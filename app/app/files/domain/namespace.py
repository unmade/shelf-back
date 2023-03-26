from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

__all__ = ["Namespace"]


class NamespaceNotFound(Exception):
    pass


class Namespace(BaseModel):
    NotFound = NamespaceNotFound

    id: UUID
    path: str
    owner_id: UUID
