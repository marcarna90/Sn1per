"""The engine-independent result record (ADR 0008)."""

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from neo_orchestro.core.enums import FindingCategory, Severity


class NormalisedFinding(BaseModel):
    """Every engine maps its native output to this shape.

    ``key`` is the engine-chosen *identity* of the finding (e.g. ``"A:93.184.216.34"``);
    volatile data such as TTLs belongs in ``evidence`` and does not affect the fingerprint.
    """

    model_config = ConfigDict(frozen=True)

    category: FindingCategory
    severity: Severity
    title: str = Field(max_length=300)
    asset: str = Field(max_length=255)
    description: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    key: str = Field(default="", max_length=500)

    @property
    def fingerprint(self) -> str:
        """SHA-256 over an unambiguous encoding of the identity fields."""
        identity = json.dumps(
            [self.category.value, self.asset, self.title, self.key],
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return hashlib.sha256(identity.encode("ascii")).hexdigest()
