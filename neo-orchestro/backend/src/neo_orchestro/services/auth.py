"""Authentication: login with lockout, rotating refresh tokens with reuse detection (ADR 0005)."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import NoReturn

from sqlalchemy.orm import Session

from neo_orchestro.core.config import Settings
from neo_orchestro.core.enums import AuditOutcome
from neo_orchestro.core.errors import AuthenticationError
from neo_orchestro.core.security import (
    TokenType,
    decode_token,
    hash_password,
    issue_access_token,
    issue_refresh_token,
    needs_rehash,
    spend_hashing_time,
    validate_password,
    verify_password,
)
from neo_orchestro.db.models import RefreshToken, User
from neo_orchestro.repositories.auth import AuthRepository
from neo_orchestro.services.audit import AuditService
from neo_orchestro.services.context import Clock, Principal, RequestContext, utc_now

_GENERIC = "invalid credentials"
_INVALID_SESSION = "invalid or expired token"


@dataclass(frozen=True, slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    access_expires_in: int
    refresh_expires_at: datetime


class AuthService:
    def __init__(self, session: Session, settings: Settings, *, clock: Clock = utc_now) -> None:
        self._session = session
        self._settings = settings
        self._clock = clock
        self._repo = AuthRepository(session)
        self._audit = AuditService(session)
        self._secret = settings.secret_key.get_secret_value()

    # ------------------------------------------------------------------ login

    def login(self, email: str, password: str, context: RequestContext | None = None) -> TokenPair:
        """Authenticate by e-mail and password.

        Every failure raises the same error (no account enumeration); the real reason is
        recorded in the audit log. Unknown accounts still cost a hash verification so the
        response time does not reveal whether the e-mail exists.
        """
        now = self._clock()
        email = email.strip().lower()
        user = self._repo.get_user_by_email(email)

        if user is None:
            spend_hashing_time(password)
            self._deny_login(None, "unknown_user", email, context)
        if user.locked_until is not None:
            if user.locked_until > now:
                spend_hashing_time(password)
                self._deny_login(user, "locked", email, context)
            user.locked_until = None  # lock expired: start counting afresh
            user.failed_login_attempts = 0
        if not user.is_active:
            spend_hashing_time(password)
            self._deny_login(user, "inactive", email, context)
        if not verify_password(user.password_hash, password):
            user.failed_login_attempts += 1
            reason = "bad_password"
            if user.failed_login_attempts >= self._settings.login_max_failed_attempts:
                user.locked_until = now + timedelta(minutes=self._settings.login_lockout_minutes)
                reason = "bad_password_locked"
            self._deny_login(user, reason, email, context)

        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = now
        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
        pair = self._issue_pair(user, family_id=uuid.uuid4(), now=now)
        self._audit.record(
            action="auth.login",
            outcome=AuditOutcome.success,
            org_id=user.org_id,
            actor_user_id=user.id,
            context=context,
        )
        self._session.commit()
        return pair

    def _deny_login(
        self, user: User | None, reason: str, email: str, context: RequestContext | None
    ) -> NoReturn:
        self._audit.record(
            action="auth.login",
            outcome=AuditOutcome.denied,
            org_id=user.org_id if user else None,
            actor_user_id=user.id if user else None,
            context=context,
            details={"reason": reason, "email": email},
        )
        self._session.commit()  # persist counters + audit even though we raise
        raise AuthenticationError(_GENERIC)

    # ------------------------------------------------------------------ refresh / logout

    def refresh(self, refresh_token: str, context: RequestContext | None = None) -> TokenPair:
        """Rotate a refresh token. Replaying an already-rotated token kills the whole family."""
        claims = decode_token(
            refresh_token,
            secret=self._secret,
            issuer=self._settings.jwt_issuer,
            token_type=TokenType.refresh,
        )
        now = self._clock()
        row = self._repo.get_refresh_token_for_update(claims.jti)
        if row is None or row.user_id != claims.subject or row.family_id != claims.family_id:
            raise AuthenticationError(_INVALID_SESSION)
        user = self._repo.get_user(row.user_id)

        if row.revoked_at is not None:
            # A revoked token is only a theft signal while its family is still alive: that is
            # the "rotated token replayed" case. A token of an already-dead family (after a
            # logout, a deactivation, or a previous reuse alert) is just refused, quietly.
            still_alive = self._repo.revoke_family(row.family_id, now)
            self._audit.record(
                action="auth.refresh_reuse_detected" if still_alive else "auth.refresh",
                outcome=AuditOutcome.denied,
                org_id=user.org_id if user else None,
                actor_user_id=row.user_id,
                context=context,
                details={"family_id": str(row.family_id)}
                if still_alive
                else {"reason": "revoked_token"},
            )
            self._session.commit()
            raise AuthenticationError(_INVALID_SESSION)
        if row.expires_at <= now:
            raise AuthenticationError(_INVALID_SESSION)
        if user is None or not user.is_active:
            self._repo.revoke_family(row.family_id, now)
            self._audit.record(
                action="auth.refresh",
                outcome=AuditOutcome.denied,
                org_id=user.org_id if user else None,
                actor_user_id=row.user_id,
                context=context,
                details={"reason": "inactive"},
            )
            self._session.commit()
            raise AuthenticationError(_INVALID_SESSION)

        row.revoked_at = now
        pair = self._issue_pair(user, family_id=row.family_id, now=now)
        self._audit.record(
            action="auth.refresh",
            outcome=AuditOutcome.success,
            org_id=user.org_id,
            actor_user_id=user.id,
            context=context,
        )
        self._session.commit()
        return pair

    def logout(self, refresh_token: str, context: RequestContext | None = None) -> None:
        """Revoke the session behind a refresh token. Idempotent; never reveals token validity."""
        try:
            claims = decode_token(
                refresh_token,
                secret=self._secret,
                issuer=self._settings.jwt_issuer,
                token_type=TokenType.refresh,
            )
        except AuthenticationError:
            return
        row = self._repo.get_refresh_token(claims.jti)
        if row is None:
            return
        self._repo.revoke_family(row.family_id, self._clock())
        user = self._repo.get_user(row.user_id)
        self._audit.record(
            action="auth.logout",
            outcome=AuditOutcome.success,
            org_id=user.org_id if user else None,
            actor_user_id=row.user_id,
            context=context,
        )
        self._session.commit()

    # ------------------------------------------------------------------ per-request

    def authenticate(self, access_token: str) -> Principal:
        """Validate an access token and return the caller as the database sees them *now*.

        Role, activity and organisation are re-read on every request so deactivation and
        demotion take effect immediately instead of when the token expires.
        """
        claims = decode_token(
            access_token,
            secret=self._secret,
            issuer=self._settings.jwt_issuer,
            token_type=TokenType.access,
        )
        user = self._repo.get_user(claims.subject)
        if user is None or not user.is_active or claims.org_id != user.org_id:
            raise AuthenticationError(_INVALID_SESSION)
        return Principal(user_id=user.id, org_id=user.org_id, role=user.role, email=user.email)

    def profile(self, principal: Principal) -> User:
        """The caller's own user record (never another tenant's: the id comes from the token)."""
        user = self._repo.get_user(principal.user_id)
        if user is None or user.org_id != principal.org_id:
            raise AuthenticationError(_INVALID_SESSION)
        return user

    # ------------------------------------------------------------------ password

    def change_password(
        self,
        principal: Principal,
        old_password: str,
        new_password: str,
        context: RequestContext | None = None,
    ) -> None:
        """Self-service password change; revokes every session of the user."""
        user = self._repo.get_user(principal.user_id)
        if user is None or not verify_password(user.password_hash, old_password):
            self._audit.record_by(
                principal,
                action="auth.change_password",
                outcome=AuditOutcome.denied,
                context=context,
                details={"reason": "bad_password"},
            )
            self._session.commit()
            raise AuthenticationError(_GENERIC)
        validate_password(new_password, email=user.email)
        user.password_hash = hash_password(new_password)
        self._repo.revoke_user_tokens(user.id, self._clock())
        self._audit.record_by(
            principal, action="auth.change_password", outcome=AuditOutcome.success, context=context
        )
        self._session.commit()

    # ------------------------------------------------------------------ helpers

    def _issue_pair(self, user: User, *, family_id: uuid.UUID, now: datetime) -> TokenPair:
        access_ttl = timedelta(minutes=self._settings.access_token_ttl_minutes)
        refresh_expires = now + timedelta(days=self._settings.refresh_token_ttl_days)
        jti = uuid.uuid4()
        self._repo.add_refresh_token(
            RefreshToken(id=jti, user_id=user.id, family_id=family_id, expires_at=refresh_expires)
        )
        return TokenPair(
            access_token=issue_access_token(
                user_id=user.id,
                org_id=user.org_id,
                role=user.role,
                secret=self._secret,
                issuer=self._settings.jwt_issuer,
                ttl=access_ttl,
                now=now,
            ),
            refresh_token=issue_refresh_token(
                user_id=user.id,
                jti=jti,
                family_id=family_id,
                secret=self._secret,
                issuer=self._settings.jwt_issuer,
                expires_at=refresh_expires,
                now=now,
            ),
            access_expires_in=int(access_ttl.total_seconds()),
            refresh_expires_at=refresh_expires,
        )
