"""Shared test configuration.

Environment is prepared *before* any application module is imported so that
`Settings` never reads a developer's real `.env`.
"""

import os
import secrets

os.environ.setdefault("NEO_ENV", "test")
os.environ.setdefault("NEO_SECRET_KEY", secrets.token_urlsafe(48))
