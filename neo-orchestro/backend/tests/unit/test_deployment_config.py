"""Deployment files that tests cannot run but can still guard against known regressions."""

import re
from pathlib import Path

import pytest

NGINX_CONF = Path(__file__).resolve().parents[3] / "frontend" / "nginx" / "default.conf"


@pytest.mark.unit
def test_nginx_resolves_the_api_per_request_not_once_at_startup() -> None:
    # Regression found by the first real Docker run: `proxy_pass http://api:8000` is resolved
    # when nginx starts. Recreating the api container (every upgrade) gives it a new IP, and nginx
    # kept proxying to the old one: HTTP 502 until `web` was restarted by hand.
    text = NGINX_CONF.read_text()
    targets = [m.strip() for m in re.findall(r"^\s*proxy_pass\s+([^;]+);", text, re.MULTILINE)]
    assert targets, "no proxy_pass found: update this test"
    literal = [t for t in targets if not t.startswith("$")]
    assert not literal, f"proxy_pass with a literal host is resolved once at start-up: {literal}"
    assert re.search(r"^\s*resolver\s+127\.0\.0\.11\b", text, re.MULTILINE), (
        "variables in proxy_pass need a resolver (Docker's embedded DNS is 127.0.0.11)"
    )
