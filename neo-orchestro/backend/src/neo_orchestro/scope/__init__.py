"""Scope engine: decides which targets may be scanned (ADR 0004).

Pure policy code: imports nothing from the database, API or orchestrator layers.
"""

from neo_orchestro.scope.engine import RedirectGuard, ScopeEngine
from neo_orchestro.scope.network import classify_ip, normalise_ip
from neo_orchestro.scope.parsing import parse_target
from neo_orchestro.scope.resolver import DnsPythonResolver, Resolver, StaticResolver
from neo_orchestro.scope.rules import build_rule
from neo_orchestro.scope.types import (
    Decision,
    DenyReason,
    InvalidScopeEntryError,
    InvalidTargetError,
    IpClass,
    NoSuchDomainError,
    ParsedTarget,
    ResolutionError,
    ScopeLimits,
    ScopeRule,
)

__all__ = [
    "Decision",
    "DenyReason",
    "DnsPythonResolver",
    "InvalidScopeEntryError",
    "InvalidTargetError",
    "IpClass",
    "NoSuchDomainError",
    "ParsedTarget",
    "RedirectGuard",
    "ResolutionError",
    "Resolver",
    "ScopeEngine",
    "ScopeLimits",
    "ScopeRule",
    "StaticResolver",
    "build_rule",
    "classify_ip",
    "normalise_ip",
    "parse_target",
]
