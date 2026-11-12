"""Unauthenticated metadata."""

from fastapi import APIRouter

from neo_orchestro import SIGNATURE, __version__
from neo_orchestro.api.schemas import MetaOut

router = APIRouter(tags=["system"])


@router.get("/meta", response_model=MetaOut, summary="Name, version and signature")
def meta() -> MetaOut:
    return MetaOut(name="Neo-Orchestro", version=__version__, signature=SIGNATURE)
