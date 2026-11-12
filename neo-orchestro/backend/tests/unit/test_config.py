"""Settings: secure by default, strict in production."""

import pytest
from pydantic import ValidationError

from neo_orchestro.core.config import Settings

GOOD_KEY = "k" * 48
GOOD_DB = "postgresql+pg8000://neo:s3cret@db:5432/neo"
GOOD_REDIS = "redis://:s3cret@redis:6379/0"


def make(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "secret_key": GOOD_KEY,
        "database_url": GOOD_DB,
        "redis_url": GOOD_REDIS,
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type]


@pytest.mark.unit
def test_development_defaults_are_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEO_ENV", raising=False)
    s = make()
    assert s.env == "development"
    assert s.access_token_ttl_minutes == 15
    assert s.login_max_failed_attempts == 5
    assert s.cors_origins == []
    assert s.scope_min_prefix_v4 == 16


@pytest.mark.unit
def test_secret_key_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEO_SECRET_KEY", raising=False)
    with pytest.raises(ValidationError, match="secret_key"):
        Settings(_env_file=None, database_url=GOOD_DB, redis_url=GOOD_REDIS)  # type: ignore[call-arg]


@pytest.mark.unit
def test_short_secret_key_is_rejected() -> None:
    with pytest.raises(ValidationError, match="secret_key"):
        make(secret_key="too-short")


@pytest.mark.unit
def test_secrets_are_not_leaked_by_repr() -> None:
    shown = repr(make())
    assert GOOD_KEY not in shown
    assert "s3cret" not in shown  # DB and Redis passwords live in the URLs


@pytest.mark.unit
def test_production_requires_secure_cookie() -> None:
    with pytest.raises(ValidationError, match="cookie_secure"):
        make(env="production", cookie_secure=False)


@pytest.mark.unit
def test_production_rejects_placeholder_credentials() -> None:
    with pytest.raises(ValidationError, match="CHANGE_ME"):
        make(
            env="production",
            cookie_secure=True,
            database_url="postgresql+pg8000://neo:CHANGE_ME@db:5432/neo",
        )


@pytest.mark.unit
def test_production_disables_api_docs_by_default() -> None:
    assert make(env="production", cookie_secure=True).docs_enabled is False
    assert make(env="development").docs_enabled is True


@pytest.mark.unit
def test_only_the_postgres_pg8000_driver_is_accepted() -> None:
    with pytest.raises(ValidationError, match="database_url"):
        make(database_url="sqlite:///x.db")


@pytest.mark.unit
def test_cors_origins_parse_from_comma_separated_string() -> None:
    s = make(cors_origins="https://a.example, https://b.example")
    assert s.cors_origins == ["https://a.example", "https://b.example"]


@pytest.mark.unit
def test_wildcard_cors_origin_is_rejected() -> None:
    with pytest.raises(ValidationError, match="cors_origins"):
        make(cors_origins="*")


@pytest.mark.unit
def test_dns_nameservers_default_to_the_system_resolver() -> None:
    assert make().dns_nameservers == []


@pytest.mark.unit
def test_dns_nameservers_parse_from_a_comma_separated_string() -> None:
    s = make(dns_nameservers="9.9.9.9, 2606:4700:4700::1111")
    assert s.dns_nameservers == ["9.9.9.9", "2606:4700:4700::1111"]


@pytest.mark.unit
@pytest.mark.parametrize(
    "bad", ["dns.example.com", "9.9.9", "9.9.9.9:53", "not an ip", "9.9.9.9;8.8.8.8"]
)
def test_dns_nameservers_must_be_ip_addresses(bad: str) -> None:
    with pytest.raises(ValidationError, match="dns_nameservers"):
        make(dns_nameservers=bad)
