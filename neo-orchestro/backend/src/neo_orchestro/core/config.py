"""Application settings, loaded from ``NEO_*`` environment variables.

Secure by default: secrets are required and never shown in ``repr``;
production mode refuses insecure combinations (ADR 0005).
"""

from functools import lru_cache
from ipaddress import ip_address
from typing import Annotated, Any, Literal, Self

from pydantic import BeforeValidator, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_PLACEHOLDER = "CHANGE_ME"


def _split_csv(value: Any) -> Any:
    """Accept ``"a, b"`` from the environment as well as a real list."""
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return value


class Settings(BaseSettings):
    """Typed configuration. Construct via :func:`get_settings` in application code."""

    model_config = SettingsConfigDict(
        env_prefix="NEO_", env_file=".env", extra="ignore", case_sensitive=False
    )

    env: Literal["development", "test", "production"] = "development"

    # --- secrets (SecretStr => hidden from repr/logs) ---------------------------------
    secret_key: SecretStr
    database_url: SecretStr
    redis_url: SecretStr

    # --- authentication ---------------------------------------------------------------
    access_token_ttl_minutes: int = Field(default=15, ge=1, le=120)
    refresh_token_ttl_days: int = Field(default=7, ge=1, le=90)
    login_max_failed_attempts: int = Field(default=5, ge=3, le=20)
    login_lockout_minutes: int = Field(default=15, ge=1, le=1440)
    cookie_secure: bool = False
    jwt_issuer: str = "neo-orchestro"

    # --- HTTP -------------------------------------------------------------------------
    cors_origins: Annotated[list[str], NoDecode, BeforeValidator(_split_csv)] = []
    docs_enabled: bool = True

    # --- observability ----------------------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_json: bool = False
    metrics_enabled: bool = True

    # --- scope engine -----------------------------------------------------------------
    scope_min_prefix_v4: int = Field(default=16, ge=8, le=32)
    scope_min_prefix_v6: int = Field(default=48, ge=32, le=128)

    # --- scans / DNS ------------------------------------------------------------------
    scan_max_duration_seconds: int = Field(default=900, ge=10, le=86400)
    dns_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    # Empty = the host's resolver. Set explicit IPs to use a trusted resolver (ADR 0004).
    dns_nameservers: Annotated[list[str], NoDecode, BeforeValidator(_split_csv)] = []

    # --- database pool ----------------------------------------------------------------
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=5, ge=0, le=50)

    @model_validator(mode="before")
    @classmethod
    def _docs_default(cls, data: Any) -> Any:
        """API docs are on in dev/test and off in production unless set explicitly."""
        if isinstance(data, dict) and "docs_enabled" not in data:
            data = {**data, "docs_enabled": data.get("env", "development") != "production"}
        return data

    @field_validator("secret_key")
    @classmethod
    def _secret_key_strength(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("secret_key must be at least 32 characters")
        return value

    @field_validator("database_url")
    @classmethod
    def _database_driver(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith("postgresql+pg8000://"):
            raise ValueError("database_url must use the postgresql+pg8000:// driver (ADR 0003)")
        return value

    @field_validator("redis_url")
    @classmethod
    def _redis_scheme(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith(("redis://", "rediss://")):
            raise ValueError("redis_url must start with redis:// or rediss://")
        return value

    @field_validator("dns_nameservers")
    @classmethod
    def _nameservers_are_ips(cls, value: list[str]) -> list[str]:
        for item in value:
            try:
                ip_address(item)
            except ValueError:
                raise ValueError(
                    f"dns_nameservers must be IP addresses, got {item[:40]!r}"
                ) from None
        return value

    @field_validator("cors_origins")
    @classmethod
    def _no_wildcard_cors(cls, value: list[str]) -> list[str]:
        if any(origin == "*" for origin in value):
            raise ValueError("cors_origins must list explicit origins; '*' is not allowed")
        return value

    @model_validator(mode="after")
    def _production_guards(self) -> Self:
        if self.env != "production":
            return self
        if not self.cookie_secure:
            raise ValueError("cookie_secure must be true in production (HTTPS only)")
        for name in ("secret_key", "database_url", "redis_url"):
            if _PLACEHOLDER in getattr(self, name).get_secret_value():
                raise ValueError(f"{name} still contains the {_PLACEHOLDER} placeholder")
        return self


@lru_cache
def get_settings() -> Settings:
    """Process-wide settings (cached). Tests may call ``get_settings.cache_clear()``."""
    return Settings()  # required fields are supplied by the environment
