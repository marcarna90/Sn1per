"""Request and response schemas. Inputs forbid unknown fields (no mass assignment)."""

import json
import uuid
from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, model_validator

from neo_orchestro.core.enums import (
    AuditOutcome,
    FindingCategory,
    NetworkClass,
    Role,
    ScanStatus,
    ScopeKind,
    Severity,
)
from neo_orchestro.scope import DenyReason


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _FromOrm(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------------ auth


class LoginRequest(_Strict):
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=1024)


class TokenResponse(BaseModel):
    """The refresh token travels only in an HttpOnly cookie, never in the body."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105  (OAuth 2.0 field name, not a secret)
    expires_in: int


class ChangePasswordRequest(_Strict):
    old_password: SecretStr = Field(min_length=1, max_length=1024)
    new_password: SecretStr = Field(max_length=1024)  # strength rules live in the service


# ------------------------------------------------------------------ users


class UserOut(_FromOrm):
    id: uuid.UUID
    org_id: uuid.UUID
    email: str
    role: Role
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class UserCreate(_Strict):
    email: EmailStr
    password: SecretStr = Field(max_length=1024)
    role: Role


class UserUpdate(_Strict):
    role: Role | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _at_least_one_change(self) -> Self:
        if self.role is None and self.is_active is None:
            raise ValueError("provide at least one of: role, is_active")
        return self


# ------------------------------------------------------------------ scope


class ScopeEntryCreate(_Strict):
    kind: ScopeKind
    value: str = Field(min_length=1, max_length=255)
    include_subdomains: bool = False
    description: str | None = Field(default=None, max_length=500)


class ScopeEntryOut(_FromOrm):
    id: uuid.UUID
    kind: ScopeKind
    value: str
    include_subdomains: bool
    network_class: NetworkClass
    description: str | None
    created_at: datetime


class ScopeCheckRequest(_Strict):
    target: str = Field(min_length=1, max_length=255)


class DecisionOut(BaseModel):
    allowed: bool
    reason: DenyReason | None
    target: str | None
    pinned_ips: list[str]
    matched_rule_ids: list[str]
    details: dict[str, str]


# ------------------------------------------------------------------ audit / meta


class AuditLogOut(_FromOrm):
    id: int
    org_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None
    action: str
    resource_type: str | None
    resource_id: str | None
    outcome: AuditOutcome
    ip: str | None
    request_id: str | None
    details: dict[str, Any]
    created_at: datetime


class MetaOut(BaseModel):
    name: str
    version: str
    signature: str


# ------------------------------------------------------------------ scans

_MAX_PARAMS_BYTES = 8_192


class ScanCreate(_Strict):
    """Only what the client may choose. Status, organisation, requester and the scope
    decision are server-controlled and rejected if sent."""

    engine: str = Field(min_length=1, max_length=64)
    target: str = Field(min_length=1, max_length=255)
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _bounded_params(self) -> Self:
        if len(json.dumps(self.params, default=str)) > _MAX_PARAMS_BYTES:
            raise ValueError("params are too large")
        return self


class ScanOut(_FromOrm):
    id: uuid.UUID
    engine: str
    target: str
    params: dict[str, Any]
    status: ScanStatus
    error_code: str | None
    error_message: str | None
    scope_decision: dict[str, Any] | None
    requested_by_id: uuid.UUID | None
    attempts: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    cancel_requested_at: datetime | None


class FindingOut(_FromOrm):
    id: uuid.UUID
    scan_id: uuid.UUID
    category: FindingCategory
    severity: Severity
    title: str
    asset: str
    description: str | None
    evidence: dict[str, Any]
    source_engine: str
    created_at: datetime


class EngineOut(BaseModel):
    name: str
    description: str
    target_kinds: list[ScopeKind]
