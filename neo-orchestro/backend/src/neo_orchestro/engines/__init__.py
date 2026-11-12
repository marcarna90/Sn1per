"""Scan engines: ports, safe process execution, allowlist registry, concrete adapters.

Imports only ``core`` (ADR 0002). Concrete engines are registered explicitly in
:func:`default_registry`; nothing is discovered dynamically.
"""

from neo_orchestro.engines.base import Engine, EngineContext, EngineError, ScanCancelled
from neo_orchestro.engines.dns_recon import DnsPythonClient, DnsReconEngine
from neo_orchestro.engines.findings import NormalisedFinding
from neo_orchestro.engines.process import CommandResult, run_command
from neo_orchestro.engines.registry import EngineRegistry, UnknownEngineError, default_registry

__all__ = [
    "CommandResult",
    "DnsPythonClient",
    "DnsReconEngine",
    "Engine",
    "EngineContext",
    "EngineError",
    "EngineRegistry",
    "NormalisedFinding",
    "ScanCancelled",
    "UnknownEngineError",
    "default_registry",
    "run_command",
]
