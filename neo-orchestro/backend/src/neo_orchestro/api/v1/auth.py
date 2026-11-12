"""Authentication endpoints. The refresh token lives only in an HttpOnly cookie."""

from typing import Annotated

from fastapi import APIRouter, Cookie, Response

from neo_orchestro.api.deps import (
    ClockDep,
    ContextDep,
    CsrfDep,
    PrincipalDep,
    SessionDep,
    SettingsDep,
)
from neo_orchestro.api.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    TokenResponse,
    UserOut,
)
from neo_orchestro.core.config import Settings
from neo_orchestro.core.errors import AuthenticationError
from neo_orchestro.services.auth import AuthService, TokenPair

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "neo_refresh"
COOKIE_PATH = "/api/v1/auth"  # the browser only sends it to the auth endpoints


def _set_refresh_cookie(response: Response, pair: TokenPair, settings: Settings) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        pair.refresh_token,
        max_age=settings.refresh_token_ttl_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path=COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        REFRESH_COOKIE,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path=COOKIE_PATH,
    )


def _token_body(pair: TokenPair) -> TokenResponse:
    return TokenResponse(access_token=pair.access_token, expires_in=pair.access_expires_in)


@router.post("/login", response_model=TokenResponse, summary="Log in with e-mail and password")
def login(
    body: LoginRequest,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    clock: ClockDep,
    context: ContextDep,
) -> TokenResponse:
    pair = AuthService(session, settings, clock=clock).login(
        body.email, body.password.get_secret_value(), context
    )
    _set_refresh_cookie(response, pair, settings)
    return _token_body(pair)


@router.post("/refresh", response_model=TokenResponse, summary="Rotate the refresh cookie")
def refresh(
    response: Response,
    _csrf: CsrfDep,
    session: SessionDep,
    settings: SettingsDep,
    clock: ClockDep,
    context: ContextDep,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> TokenResponse:
    if not refresh_token:
        raise AuthenticationError("authentication required")
    pair = AuthService(session, settings, clock=clock).refresh(refresh_token, context)
    _set_refresh_cookie(response, pair, settings)
    return _token_body(pair)


@router.post("/logout", status_code=204, summary="Revoke the current session")
def logout(
    _csrf: CsrfDep,
    session: SessionDep,
    settings: SettingsDep,
    clock: ClockDep,
    context: ContextDep,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> Response:
    if refresh_token:
        AuthService(session, settings, clock=clock).logout(refresh_token, context)
    response = Response(status_code=204)
    _clear_refresh_cookie(response, settings)
    return response


@router.get("/me", response_model=UserOut, summary="The authenticated user")
def me(
    principal: PrincipalDep, session: SessionDep, settings: SettingsDep, clock: ClockDep
) -> object:
    return AuthService(session, settings, clock=clock).profile(principal)


@router.post("/change-password", status_code=204, summary="Change own password")
def change_password(
    body: ChangePasswordRequest,
    principal: PrincipalDep,
    session: SessionDep,
    settings: SettingsDep,
    clock: ClockDep,
    context: ContextDep,
) -> Response:
    AuthService(session, settings, clock=clock).change_password(
        principal,
        body.old_password.get_secret_value(),
        body.new_password.get_secret_value(),
        context,
    )
    response = Response(status_code=204)
    _clear_refresh_cookie(response, settings)  # every session was revoked
    return response
