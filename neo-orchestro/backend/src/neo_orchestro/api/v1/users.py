"""User management (administrators only)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from neo_orchestro.api.deps import ClockDep, ContextDep, SessionDep, require
from neo_orchestro.api.schemas import UserCreate, UserOut, UserUpdate
from neo_orchestro.core.enums import Role
from neo_orchestro.services.context import Principal
from neo_orchestro.services.users import UserService

router = APIRouter(prefix="/users", tags=["users"])
AdminDep = Annotated[Principal, Depends(require(Role.admin))]


@router.get("", response_model=list[UserOut], summary="List users of my organisation")
def list_users(principal: AdminDep, session: SessionDep, clock: ClockDep) -> object:
    return UserService(session, principal, clock=clock).list_users()


@router.post("", response_model=UserOut, status_code=201, summary="Create a user")
def create_user(
    body: UserCreate,
    principal: AdminDep,
    session: SessionDep,
    clock: ClockDep,
    context: ContextDep,
) -> object:
    return UserService(session, principal, clock=clock).create_user(
        email=body.email,
        password=body.password.get_secret_value(),
        role=body.role,
        context=context,
    )


@router.get("/{user_id}", response_model=UserOut, summary="Get a user")
def get_user(
    user_id: uuid.UUID, principal: AdminDep, session: SessionDep, clock: ClockDep
) -> object:
    return UserService(session, principal, clock=clock).get_user(user_id)


@router.patch("/{user_id}", response_model=UserOut, summary="Change role or activation")
def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    principal: AdminDep,
    session: SessionDep,
    clock: ClockDep,
    context: ContextDep,
) -> object:
    return UserService(session, principal, clock=clock).update_user(
        user_id, role=body.role, is_active=body.is_active, context=context
    )
