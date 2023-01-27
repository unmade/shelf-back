from __future__ import annotations

from typing import TYPE_CHECKING, cast

import edgedb

from app import crud, errors
from app.app.repositories import INamespaceRepository
from app.domain.entities import Namespace

if TYPE_CHECKING:
    from app.infrastructure.database.edgedb.typedefs import EdgeDBAnyConn, EdgeDBContext
    from app.typedefs import StrOrUUID

__all__ = ["NamespaceRepository"]


class NamespaceRepository(INamespaceRepository):
    def __init__(self, db_context: EdgeDBContext):
        self.db_context = db_context

    @property
    def conn(self) -> EdgeDBAnyConn:
        return self.db_context.get()

    async def get_by_path(self, path: str) -> Namespace:
        query = """
            SELECT
                Namespace {
                    id, path, owner: { id }
                }
            FILTER
                .path = <str>$path
        """

        try:
            obj = await self.conn.query_required_single(query, path=path)
        except edgedb.NoDataError as exc:
            msg = f"Namespace with path={path} does not exists"
            raise errors.NamespaceNotFound(msg) from exc

        return Namespace(id=obj.id, path=obj.path, owner_id=obj.owner.id)

    async def get_space_used_by_owner_id(self, owner_id: StrOrUUID) -> int:
        query = """
            WITH
                namespaces := (
                    SELECT
                        Namespace
                    FILTER
                        .owner.id = <uuid>$owner_id
                ),
            SELECT sum((
                SELECT
                    File { size }
                FILTER
                    .namespace IN namespaces
                    AND
                    .path = '.'
            ).size)
        """

        value = await self.conn.query_required_single(query, owner_id=owner_id)
        return cast(int, value)

    async def save(self, namespace: Namespace) -> Namespace:
        obj = await crud.namespace.create(
            self.conn,
            path=namespace.path,
            owner_id=namespace.owner_id,
        )
        return namespace.copy(update={"id": obj.id})
