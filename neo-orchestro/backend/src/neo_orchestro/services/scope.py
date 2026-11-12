"""Scope management and evaluation for one organisation."""

import uuid
from collections.abc import Iterable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from neo_orchestro.core.config import Settings
from neo_orchestro.core.enums import AuditOutcome, Role, ScopeKind
from neo_orchestro.core.errors import ConflictError, NotFoundError, ValidationFailedError
from neo_orchestro.db.models import ScopeEntry
from neo_orchestro.repositories.scope import ScopeRepository
from neo_orchestro.scope import (
    Decision,
    InvalidScopeEntryError,
    Resolver,
    ScopeEngine,
    ScopeLimits,
    ScopeRule,
    build_rule,
)
from neo_orchestro.services.audit import AuditService
from neo_orchestro.services.context import Principal, RequestContext, require_role


def to_rules(entries: Iterable[ScopeEntry]) -> list[ScopeRule]:
    """Convert stored entries to engine-ready rules (also used by the worker)."""
    return [
        ScopeRule(
            id=str(e.id),
            kind=e.kind,
            value=e.value,
            include_subdomains=e.include_subdomains,
            network_class=e.network_class,
        )
        for e in entries
    ]


class ScopeService:
    def __init__(self, session: Session, principal: Principal, settings: Settings) -> None:
        self._session = session
        self._principal = principal
        self._repo = ScopeRepository(session, principal.org_id)
        self._audit = AuditService(session)
        self._limits = ScopeLimits(
            min_prefix_v4=settings.scope_min_prefix_v4,
            min_prefix_v6=settings.scope_min_prefix_v6,
        )

    def list_entries(self) -> list[ScopeEntry]:
        return self._repo.list()

    def add_entry(
        self,
        kind: ScopeKind,
        value: str,
        *,
        include_subdomains: bool = False,
        description: str | None = None,
        context: RequestContext | None = None,
    ) -> ScopeEntry:
        require_role(self._principal, Role.admin)
        try:
            rule = build_rule(
                kind, value, include_subdomains=include_subdomains, limits=self._limits
            )
        except InvalidScopeEntryError as exc:
            self._audit.record_by(
                self._principal,
                action="scope.create",
                outcome=AuditOutcome.denied,
                resource_type="scope_entry",
                context=context,
                details={"kind": kind.value, "value": value[:255], "reason": str(exc)},
            )
            self._session.commit()
            raise ValidationFailedError(str(exc)) from exc

        entry = ScopeEntry(
            kind=rule.kind,
            value=rule.value,
            include_subdomains=rule.include_subdomains,
            network_class=rule.network_class,
            description=description,
            created_by_id=self._principal.user_id,
        )
        try:
            self._repo.add(entry)
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError("this scope entry already exists") from exc
        self._audit.record_by(
            self._principal,
            action="scope.create",
            outcome=AuditOutcome.success,
            resource_type="scope_entry",
            resource_id=entry.id,
            context=context,
            details={"kind": rule.kind.value, "value": rule.value},
        )
        self._session.commit()
        return entry

    def delete_entry(self, entry_id: uuid.UUID, context: RequestContext | None = None) -> None:
        require_role(self._principal, Role.admin)
        entry = self._repo.get(entry_id)
        if entry is None:
            raise NotFoundError("scope entry")
        details = {"kind": entry.kind.value, "value": entry.value}
        self._repo.delete(entry)
        self._audit.record_by(
            self._principal,
            action="scope.delete",
            outcome=AuditOutcome.success,
            resource_type="scope_entry",
            resource_id=entry_id,
            context=context,
            details=details,
        )
        self._session.commit()

    def rules(self) -> list[ScopeRule]:
        return to_rules(self._repo.list())

    def engine(self, resolver: Resolver) -> ScopeEngine:
        return ScopeEngine(self.rules(), resolver, limits=self._limits)

    def check(
        self, target: str, resolver: Resolver, context: RequestContext | None = None
    ) -> Decision:
        """Dry-run: would this target be allowed right now? (Resolves only in-scope names.)"""
        require_role(self._principal, Role.analyst)
        decision = self.engine(resolver).evaluate(target)
        self._audit.record_by(
            self._principal,
            action="scope.check",
            outcome=AuditOutcome.success if decision.allowed else AuditOutcome.denied,
            resource_type="target",
            context=context,
            details={
                "target": target[:255],
                "reason": decision.reason.value if decision.reason else None,
            },
        )
        self._session.commit()
        return decision
