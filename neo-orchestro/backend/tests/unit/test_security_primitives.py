"""Password hashing, password policy and JWT handling (ADR 0005)."""

import base64
import json
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from argon2 import PasswordHasher

from neo_orchestro.core.enums import Role
from neo_orchestro.core.errors import AuthenticationError, ValidationFailedError
from neo_orchestro.core.security import (
    TokenType,
    decode_token,
    hash_password,
    issue_access_token,
    issue_refresh_token,
    needs_rehash,
    validate_password,
    verify_password,
)

SECRET = "s" * 64  # >= 64 bytes so a forged HS512 token is constructible without library warnings
ISSUER = "neo-orchestro"
USER, ORG = uuid.uuid4(), uuid.uuid4()


def access(**kw: object) -> str:
    args: dict[str, object] = {
        "user_id": USER,
        "org_id": ORG,
        "role": Role.analyst,
        "secret": SECRET,
        "issuer": ISSUER,
        "ttl": timedelta(minutes=15),
    }
    args.update(kw)
    return issue_access_token(**args)  # type: ignore[arg-type]


# ---------------------------------------------------------------- passwords


@pytest.mark.unit
@pytest.mark.security
def test_passwords_are_hashed_with_argon2id_and_salted() -> None:
    first, second = hash_password("correct horse battery"), hash_password("correct horse battery")
    assert first.startswith("$argon2id$")
    assert first != second


@pytest.mark.unit
def test_verify_password_accepts_only_the_right_password() -> None:
    stored = hash_password("correct horse battery")
    assert verify_password(stored, "correct horse battery") is True
    assert verify_password(stored, "correct horse batterY") is False
    assert verify_password(stored, "") is False


@pytest.mark.unit
@pytest.mark.parametrize("garbage", ["", "not-a-hash", "$argon2id$broken", "plaintext-password"])
def test_verify_password_never_raises_on_a_corrupt_hash(garbage: str) -> None:
    assert verify_password(garbage, "whatever") is False


@pytest.mark.unit
def test_needs_rehash_detects_weak_parameters() -> None:
    assert needs_rehash(hash_password("correct horse battery")) is False
    weak = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash("correct horse battery")
    assert needs_rehash(weak) is True


@pytest.mark.unit
def test_a_strong_password_is_accepted() -> None:
    validate_password("correct horse battery", email="alice@example.com")


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.parametrize(
    "password",
    [
        "short",
        "a" * 11,
        "aaaaaaaaaaaa",
        "x" * 129,
        "alice-the-admin" + "\x00" * 3,
        "alice@example.com",
    ],
)
def test_weak_or_abusive_passwords_are_rejected(password: str) -> None:
    with pytest.raises(ValidationFailedError):
        validate_password(password, email="alice@example.com")


@pytest.mark.unit
def test_password_equal_to_the_email_local_part_is_rejected() -> None:
    with pytest.raises(ValidationFailedError):
        validate_password("administrator", email="administrator@example.com")


# ---------------------------------------------------------------- tokens


@pytest.mark.unit
def test_access_token_round_trip() -> None:
    claims = decode_token(access(), secret=SECRET, issuer=ISSUER, token_type=TokenType.access)
    assert claims.subject == USER
    assert claims.org_id == ORG
    assert claims.role is Role.analyst
    assert claims.token_type == "access"
    assert claims.family_id is None
    assert claims.expires_at > datetime.now(UTC)


@pytest.mark.unit
def test_refresh_token_round_trip() -> None:
    jti, family = uuid.uuid4(), uuid.uuid4()
    token = issue_refresh_token(
        user_id=USER,
        jti=jti,
        family_id=family,
        secret=SECRET,
        issuer=ISSUER,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    claims = decode_token(token, secret=SECRET, issuer=ISSUER, token_type=TokenType.refresh)
    assert (claims.subject, claims.jti, claims.family_id) == (USER, jti, family)
    assert claims.org_id is None


@pytest.mark.unit
@pytest.mark.security
def test_expired_tokens_are_rejected() -> None:
    old = access(now=datetime.now(UTC) - timedelta(hours=1))
    with pytest.raises(AuthenticationError):
        decode_token(old, secret=SECRET, issuer=ISSUER, token_type=TokenType.access)


@pytest.mark.unit
@pytest.mark.security
def test_wrong_secret_wrong_issuer_are_rejected() -> None:
    with pytest.raises(AuthenticationError):
        decode_token(access(), secret="t" * 64, issuer=ISSUER, token_type=TokenType.access)
    with pytest.raises(AuthenticationError):
        decode_token(
            access(issuer="someone-else"), secret=SECRET, issuer=ISSUER, token_type=TokenType.access
        )


@pytest.mark.unit
@pytest.mark.security
def test_token_types_cannot_be_confused() -> None:
    refresh = issue_refresh_token(
        user_id=USER,
        jti=uuid.uuid4(),
        family_id=uuid.uuid4(),
        secret=SECRET,
        issuer=ISSUER,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    with pytest.raises(AuthenticationError):  # refresh token presented as an access token
        decode_token(refresh, secret=SECRET, issuer=ISSUER, token_type=TokenType.access)
    with pytest.raises(AuthenticationError):  # access token presented as a refresh token
        decode_token(access(), secret=SECRET, issuer=ISSUER, token_type=TokenType.refresh)


def _forge(payload: dict[str, object], *, alg: str, key: str | None) -> str:
    return jwt.encode(payload, key or "", algorithm=alg) if alg != "none" else _unsigned(payload)


def _unsigned(payload: dict[str, object]) -> str:
    def b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header = b64(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    body = b64(json.dumps(payload).encode())
    return f"{header}.{body}."


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.parametrize("alg", ["none", "HS512", "HS384"])
def test_the_signing_algorithm_is_pinned(alg: str) -> None:
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "iss": ISSUER,
        "aud": "neo-access",
        "sub": str(USER),
        "org": str(ORG),
        "role": "admin",
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    forged = _forge(payload, alg=alg, key=SECRET)
    with pytest.raises(AuthenticationError):
        decode_token(forged, secret=SECRET, issuer=ISSUER, token_type=TokenType.access)


@pytest.mark.unit
@pytest.mark.security
def test_a_token_without_expiry_is_rejected() -> None:
    payload: dict[str, object] = {
        "iss": ISSUER,
        "aud": "neo-access",
        "sub": str(USER),
        "org": str(ORG),
        "role": "viewer",
        "jti": str(uuid.uuid4()),
    }
    forged = jwt.encode(payload, SECRET, algorithm="HS256")
    with pytest.raises(AuthenticationError):
        decode_token(forged, secret=SECRET, issuer=ISSUER, token_type=TokenType.access)


@pytest.mark.unit
@pytest.mark.security
def test_a_tampered_payload_is_rejected() -> None:
    header, _payload, signature = access().split(".")
    evil = base64.urlsafe_b64encode(
        json.dumps({"sub": str(USER), "role": "admin"}).encode()
    ).rstrip(b"=")
    with pytest.raises(AuthenticationError):
        decode_token(
            f"{header}.{evil.decode()}.{signature}",
            secret=SECRET,
            issuer=ISSUER,
            token_type=TokenType.access,
        )


@pytest.mark.unit
@pytest.mark.parametrize("garbage", ["", "abc", "a.b.c", "....", "Bearer x", "\x00"])
def test_garbage_tokens_are_rejected_cleanly(garbage: str) -> None:
    with pytest.raises(AuthenticationError):
        decode_token(garbage, secret=SECRET, issuer=ISSUER, token_type=TokenType.access)
