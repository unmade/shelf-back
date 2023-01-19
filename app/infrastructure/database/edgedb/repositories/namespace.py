from __future__ import annotations

from app import crud
from app.app.repositories import INamespaceRepository
from app.domain.entities import Namespace


class NamespaceRepository(INamespaceRepository):
    def __init__(self, db_context):
        self.db_context = db_context

    @property
    def conn(self):
        return self.db_context.get()

    async def save(self, namespace: Namespace) -> Namespace:
        created_ns = await crud.namespace.create(
            self.conn,
            path=namespace.path,
            owner_id=namespace.owner_id,
        )
        return namespace.copy(update={"id": created_ns.id})
