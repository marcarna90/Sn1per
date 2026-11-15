"""The runtime lock must hold everything the container needs, not what dev tools drag in.

Regression: the worker crashed at start-up in the Docker image with
``ModuleNotFoundError: No module named 'packaging'``. kombu's Redis transport imports
``packaging`` but declares it only in its ``redis`` extra; the project asked for ``celery`` and
``redis`` separately, so the runtime lock lacked it. Every test passed because pytest (dev
dependency) installs ``packaging`` in the development environment.
"""

import re
from importlib.metadata import requires
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

BACKEND_DIR = Path(__file__).resolve().parents[2]

# (distribution, extra) pairs whose optional dependencies the code really needs at runtime.
RELIED_ON_EXTRAS = [("kombu", "redis")]


def locked_names() -> set[str]:
    names: set[str] = set()
    for line in (BACKEND_DIR / "requirements.txt").read_text().splitlines():
        match = re.match(r"^([A-Za-z0-9_.\-]+)==", line)
        if match:
            names.add(canonicalize_name(match.group(1)))
    return names


def extra_requirements(distribution: str, extra: str) -> set[str]:
    needed: set[str] = set()
    for raw in requires(distribution) or []:
        requirement = Requirement(raw)
        marker = requirement.marker
        if marker and marker.evaluate({"extra": extra}) and not marker.evaluate({"extra": ""}):
            needed.add(canonicalize_name(requirement.name))
    return needed


@pytest.mark.unit
@pytest.mark.parametrize(("distribution", "extra"), RELIED_ON_EXTRAS)
def test_runtime_lock_contains_the_extras_the_code_relies_on(distribution: str, extra: str) -> None:
    needed = extra_requirements(distribution, extra)
    assert needed, f"{distribution}[{extra}] declares nothing: update RELIED_ON_EXTRAS"
    missing = sorted(needed - locked_names())
    assert not missing, (
        f"requirements.txt lacks {missing}, required by {distribution}[{extra}]; "
        "declare the extra in pyproject.toml and run `make lock`"
    )
