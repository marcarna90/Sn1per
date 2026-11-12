"""FastAPI dependencies: session, settings, clock, resolver, request context, RBAC, CSRF."""

from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from neo_orchestro.core.config import Settings
from neo_orchestro.core.enums import Role
from neo_orchestro.core.errors import AuthenticationError, PermissionDeniedError
from neo_orchestro.engines import EngineRegistry
from neo_orchestro.scope import DnsPythonResolver, Resolver
from neo_orchestro.services.auth import AuthService
from neo_orchestro.services.context import Clock, Principal, RequestContext, require_role, utc_now
from neo_orchestro.services.scans import ScanDispatcher

_bearer = HTTPBearer(auto_error=False, description="Short-lived access token")


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


def get_session(request: Request) -> Iterator[Session]:
    session: Session = request.app.state.session_factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


SessionDep = Annotated[Session, Depends(get_session)]


def get_clock() -> Clock:
    return utc_now


ClockDep = Annotated[Clock, Depends(get_clock)]


def get_resolver(settings: SettingsDep) -> Resolver:
    return DnsPythonResolver(
        timeout=settings.dns_timeout_seconds, nameservers=settings.dns_nameservers
    )


ResolverDep = Annotated[Resolver, Depends(get_resolver)]


def get_registry(request: Request) -> EngineRegistry:
    registry: EngineRegistry = request.app.state.registry
    return registry


RegistryDep = Annotated[EngineRegistry, Depends(get_registry)]


def get_dispatcher(request: Request) -> ScanDispatcher:
    dispatcher: ScanDispatcher = request.app.state.dispatcher
    return dispatcher


DispatcherDep = Annotated[ScanDispatcher, Depends(get_dispatcher)]


def get_context(request: Request) -> RequestContext:
    return RequestContext(
        ip=request.client.host if request.client else None,
        request_id=getattr(request.state, "request_id", None),
    )


ContextDep = Annotated[RequestContext, Depends(get_context)]


def get_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: SessionDep,
    settings: SettingsDep,
    clock: ClockDep,
) -> Principal:
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("authentication required")
    return AuthService(session, settings, clock=clock).authenticate(credentials.credentials)


PrincipalDep = Annotated[Principal, Depends(get_principal)]


def require(minimum: Role) -> Callable[[Principal], Principal]:
    """Early RBAC gate for a route (services enforce again: defence in depth)."""

    def _check(principal: PrincipalDep) -> Principal:
        require_role(principal, minimum)
        return principal

    return _check


def require_csrf_header(x_neo_csrf: Annotated[str | None, Header()] = None) -> None:
    """Cookie-authenticated endpoints need a custom header a cross-site form cannot send."""
    if x_neo_csrf != "1":
        raise PermissionDeniedError("missing or invalid CSRF header")


CsrfDep = Annotated[None, Depends(require_csrf_header)]
