"""Version 1 of the public API (mounted under ``/api/v1``)."""

from fastapi import APIRouter

from neo_orchestro.api.v1 import audit, auth, scans, scope, system, users

router = APIRouter()
for module in (system, auth, users, scope, scans, audit):
    router.include_router(module.router)
