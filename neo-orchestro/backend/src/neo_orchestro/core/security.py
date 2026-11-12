"""Password hashing, password policy and JWT handling (ADR 0005).

* Passwords: Argon2id (argon2-cffi defaults = RFC 9106 "low memory" profile).
* Tokens: HS256 **pinned** (``alg=none`` and algorithm-confusion are rejected), mandatory
  ``exp``/``iat``/``iss``/``aud``/``sub``/``jti``, and a distinct audience per token
  type so an access token can never be used as a refresh token or vice versa.
"""

import enum
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import cache

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from neo_orchestro.core.enums import Role
from neo_orchestro.core.errors import AuthenticationError, ValidationFailedError


class TokenType(enum.StrEnum):
    access = "access"
    refresh = "refresh"


_ALGORITHM = "HS256"
_AUDIENCE: dict[TokenType, str] = {
    TokenType.access: "neo-access",
    TokenType.refresh: "neo-refresh",
}
_REQUIRED_CLAIMS = ["exp", "iat", "iss", "aud", "sub", "jti"]

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128

_hasher = PasswordHasher()


# ------------------------------------------------------------------ passwords


def hash_password(password: str) -> str:
    """Argon2id hash with a random salt, in PHC string format."""
    return _hasher.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    """Constant-time verification. Never raises: a corrupt hash is simply a mismatch."""
    try:
        return _hasher.verify(stored_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    """True when the stored hash uses weaker parameters than the current policy."""
    try:
        return _hasher.check_needs_rehash(stored_hash)
    except InvalidHashError:
        return True


@cache
def _dummy_hash() -> str:
    return hash_password("neo-orchestro-timing-equaliser")


def spend_hashing_time(password: str) -> None:
    """Verify against a throw-away hash so unknown accounts cost as much as known ones."""
    verify_password(_dummy_hash(), password)


def validate_password(password: str, *, email: str | None = None) -> None:
    """Length-based policy (NIST SP 800-63B): no composition rules, but no trivial secrets.

    Raises:
        ValidationFailedError: the password is unacceptable.
    """
    if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        raise ValidationFailedError(
            f"password must be between {PASSWORD_MIN_LENGTH} and {PASSWORD_MAX_LENGTH} characters"
        )
    if any(unicodedata.category(char)[0] == "C" for char in password):
        raise ValidationFailedError("password must not contain control characters")
    if len(set(password)) < 4:
        raise ValidationFailedError("password is too repetitive")
    if email:
        lowered = password.lower()
        address = email.lower()
        if lowered in {address, address.split("@", 1)[0]}:
            raise ValidationFailedError("password must not be derived from the e-mail address")


# ------------------------------------------------------------------ tokens


@dataclass(frozen=True, slots=True)
class TokenClaims:
    subject: uuid.UUID
    token_type: TokenType
    jti: uuid.UUID
    expires_at: datetime
    org_id: uuid.UUID | None = None
    role: Role | None = None
    family_id: uuid.UUID | None = None


def issue_access_token(
    *,
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    role: Role,
    secret: str,
    issuer: str,
    ttl: timedelta,
    now: datetime | None = None,
) -> str:
    issued = now or datetime.now(UTC)
    payload = {
        "iss": issuer,
        "aud": _AUDIENCE[TokenType.access],
        "sub": str(user_id),
        "org": str(org_id),
        "role": role.value,
        "jti": str(uuid.uuid4()),
        "iat": int(issued.timestamp()),
        "exp": int((issued + ttl).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def issue_refresh_token(
    *,
    user_id: uuid.UUID,
    jti: uuid.UUID,
    family_id: uuid.UUID,
    secret: str,
    issuer: str,
    expires_at: datetime,
    now: datetime | None = None,
) -> str:
    issued = now or datetime.now(UTC)
    payload = {
        "iss": issuer,
        "aud": _AUDIENCE[TokenType.refresh],
        "sub": str(user_id),
        "fam": str(family_id),
        "jti": str(jti),
        "iat": int(issued.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def decode_token(token: str, *, secret: str, issuer: str, token_type: TokenType) -> TokenClaims:
    """Validate signature, algorithm, issuer, audience and expiry.

    Raises:
        AuthenticationError: for *any* defect, with a deliberately uninformative message.
    """
    try:
        data = jwt.decode(
            token,
            secret,
            algorithms=[_ALGORITHM],
            audience=_AUDIENCE[token_type],
            issuer=issuer,
            options={"require": _REQUIRED_CLAIMS},
        )
        return TokenClaims(
            subject=uuid.UUID(data["sub"]),
            token_type=token_type,
            jti=uuid.UUID(data["jti"]),
            expires_at=datetime.fromtimestamp(data["exp"], UTC),
            org_id=uuid.UUID(data["org"]) if "org" in data else None,
            role=Role(data["role"]) if "role" in data else None,
            family_id=uuid.UUID(data["fam"]) if "fam" in data else None,
        )
    except (jwt.PyJWTError, ValueError, KeyError, TypeError) as exc:
        raise AuthenticationError("invalid or expired token") from exc
