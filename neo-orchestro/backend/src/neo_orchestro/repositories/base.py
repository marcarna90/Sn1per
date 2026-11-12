"""Tenant-scoped repository base."""

import uuid

from sqlalchemy.orm import Session


class TenantRepository:
    """Base of every repository that reads or writes business data.

    It cannot be constructed without an ``org_id``, and subclasses add that id to every
    query, so "forgetting the tenant filter" is not expressible in service or router code.
    """

    def __init__(self, session: Session, org_id: uuid.UUID) -> None:
        self._session = session
        self._org_id = org_id
