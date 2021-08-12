from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import edgedb

from app import errors
from app.entities import Namespace, User

if TYPE_CHECKING:
    from app.typedefs import DBAnyConn, StrOrPath


def namespace_from_db(obj: edgedb.Object) -> Namespace:
    return Namespace.construct(
        id=obj.id,
        path=Path(obj.path),
        owner=User.from_orm(obj.owner),
    )


async def get(conn: DBAnyConn, path: StrOrPath) -> Namespace:
    """
    Returns namespace with a target path.

    Args:
        conn (DBAnyConn): Database connection.
        path (StrOrPath): Namespace path.

    Raises:
        errors.NamespaceNotFound: If namespace with a target path does not exists.

    Returns:
        Namespace: Namespace with a target path.
    """
    query = """
        SELECT
            Namespace {
                id, path, owner: { id, username, superuser }
            }
        FILTER
            .path = <str>$path
    """

    try:
        return namespace_from_db(await conn.query_one(query, path=str(path)))
    except edgedb.NoDataError as exc:
        raise errors.NamespaceNotFound() from exc


async def get_by_owner(conn: DBAnyConn, owner_id: str) -> Namespace:
    query = """
        SELECT
            Namespace {
                id, path, owner: { id, username, superuser }
            }
        FILTER
            .owner.id = <uuid>$owner_id
    """
    try:
        return namespace_from_db(await conn.query_one(query, owner_id=owner_id))
    except edgedb.NoDataError as exc:
        raise errors.NamespaceNotFound() from exc
