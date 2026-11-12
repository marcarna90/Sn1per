"""Engine allowlist. Engines are registered in code only: never from user input or config."""

import re
from collections.abc import Iterable

from neo_orchestro.core.config import Settings
from neo_orchestro.engines.base import Engine
from neo_orchestro.engines.dns_recon import DnsPythonClient, DnsReconEngine

_NAME = re.compile(r"^[a-z][a-z0-9_]{1,31}$")


class UnknownEngineError(KeyError):
    """The requested engine is not on the allowlist."""


class EngineRegistry:
    def __init__(self, engines: Iterable[Engine] = ()) -> None:
        self._engines: dict[str, Engine] = {}
        for engine in engines:
            self.register(engine)

    def register(self, engine: Engine) -> None:
        if not _NAME.fullmatch(engine.name):
            raise ValueError(f"invalid engine name: {engine.name!r}")
        if engine.name in self._engines:
            raise ValueError(f"engine {engine.name!r} is already registered")
        self._engines[engine.name] = engine

    def get(self, name: str) -> Engine:
        try:
            return self._engines[name]
        except (KeyError, TypeError):
            raise UnknownEngineError(name[:60] if isinstance(name, str) else "?") from None

    def all(self) -> list[Engine]:
        return sorted(self._engines.values(), key=lambda e: e.name)


def default_registry(settings: Settings) -> EngineRegistry:
    """The production allowlist. Add new engines here, deliberately, one at a time."""
    return EngineRegistry([DnsReconEngine(DnsPythonClient(timeout=settings.dns_timeout_seconds))])
