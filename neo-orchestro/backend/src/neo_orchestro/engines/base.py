"""Engine port: what the orchestrator needs from a scan engine."""

import time
import uuid
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from neo_orchestro.core.enums import ScopeKind
from neo_orchestro.engines.findings import NormalisedFinding


class EngineError(Exception):
    """A scan failed in an expected way. ``code`` is stable and safe to show to users."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ScanCancelled(Exception):  # noqa: N818  (control-flow signal, not an error)
    """Raised by :meth:`EngineContext.check` when the user asked to stop."""


@dataclass(frozen=True, slots=True)
class EngineContext:
    """Everything an engine may use. ``pinned_ips`` are the scope-validated addresses.

    Engines that *connect* to the target must connect to ``pinned_ips`` and never
    re-resolve the host name (ADR 0004).
    """

    scan_id: uuid.UUID
    target: str
    pinned_ips: tuple[str, ...]
    params: Mapping[str, Any]
    is_cancelled: Callable[[], bool]
    deadline: float | None = None  # time.monotonic() timestamp

    def check(self) -> None:
        """Call frequently: honours cancellation and the maximum scan duration."""
        if self.is_cancelled():
            raise ScanCancelled
        if self.deadline is not None and time.monotonic() > self.deadline:
            raise EngineError("timeout", "scan exceeded its maximum duration")


class Engine(Protocol):
    name: str
    description: str
    target_kinds: frozenset[ScopeKind]

    def validate_params(self, params: Mapping[str, Any]) -> dict[str, Any]:
        """Return normalised parameters or raise ``EngineError("invalid_params", ...)``."""
        ...

    def run(self, ctx: EngineContext) -> Iterator[NormalisedFinding]: ...
