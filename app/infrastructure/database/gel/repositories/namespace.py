from __future__ import annotations

from typing import TYPE_CHECKING, cast

import gel

from app.app.files.domain import Namespace
from app.app.files.repositories import INamespaceRepository

if TYPE_CHECKING:
    from app.app.files.domain import AnyPath
    from app.infrastructure.database.gel.typedefs import GelAnyConn, GelContext
    from app.typedefs import StrOrUUID

__all__ = ["NamespaceRepository"]


def _from_db(obj) -> Namespace:
    return Namespace(
        id=obj.id,
        path=obj.path,
        owner_id=obj.owner.id,
    )


class NamespaceRepository(INamespaceRepository):
    def __init__(self, db_context: GelContext):
        self.db_context = db_context

    @property
    def conn(self) -> GelAnyConn:
        return self.db_context.get()

    async def get_by_owner_id(self, owner_id: StrOrUUID) -> Namespace:
        query = """
            SELECT
                Namespace {
                    id, path, owner: { id }
                }
            FILTER
                .owner.id = <uuid>$owner_id
            LIMIT 1
        """
        try:
            obj = await self.conn.query_required_single(query, owner_id=owner_id)
        except gel.NoDataError as exc:
            msg = f"Namespace with owner_id={owner_id} does not exists"
            raise Namespace.NotFound(msg) from exc
        return _from_db(obj)

    async def get_by_path(self, path: AnyPath) -> Namespace:
        query = """
            SELECT
                Namespace {
                    id, path, owner: { id }
                }
            FILTER
                .path = <str>$path
        """

        try:
            obj = await self.conn.query_required_single(query, path=str(path))
        except gel.NoDataError as exc:
            msg = f"Namespace with path={path} does not exists"
            raise Namespace.NotFound(msg) from exc

        return _from_db(obj)

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
        query = """
            SELECT (
                INSERT Namespace {
                    path := <str>$path,
                    owner := (
                        SELECT
                            User
                        FILTER
                            .id = <uuid>$owner_id
                    )
                }
            ) { id, path, owner: { id } }
        """

        obj = await self.conn.query_required_single(
            query, path=str(namespace.path), owner_id=namespace.owner_id
        )
        return _from_db(obj)
