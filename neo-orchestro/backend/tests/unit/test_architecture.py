"""Import-direction rules from ADR 0002, enforced on the source tree."""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "neo_orchestro"

# package -> packages it must NOT import from
FORBIDDEN: dict[str, set[str]] = {
    "core": {"db", "scope", "repositories", "services", "api", "orchestrator"},
    "scope": {"db", "repositories", "services", "api", "orchestrator"},
    "db": {"repositories", "services", "api", "orchestrator", "scope"},
    "repositories": {"services", "api", "orchestrator"},
    "services": {"api"},
    "orchestrator": {"api"},
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
        elif isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
    return found


@pytest.mark.unit
@pytest.mark.parametrize("package", sorted(FORBIDDEN))
def test_layers_do_not_import_upwards(package: str) -> None:
    root = SRC / package
    if not root.exists():
        pytest.skip(f"{package} not created yet")
    violations = []
    for path in root.rglob("*.py"):
        for module in _imports(path):
            parts = module.split(".")
            if parts[0] == "neo_orchestro" and len(parts) > 1 and parts[1] in FORBIDDEN[package]:
                violations.append(f"{path.relative_to(SRC)} imports {module}")
    assert not violations, "\n".join(violations)


@pytest.mark.unit
def test_routers_do_not_touch_the_database_layer_directly() -> None:
    """Routers parse → call a service → serialise (ADR 0002)."""
    api = SRC / "api"
    if not api.exists():
        pytest.skip("api not created yet")
    offenders = []
    for path in (api / "v1").rglob("*.py") if (api / "v1").exists() else []:
        for module in _imports(path):
            if module.startswith(("neo_orchestro.db.models", "sqlalchemy")):
                offenders.append(f"{path.relative_to(SRC)} imports {module}")
    assert not offenders, "\n".join(offenders)
