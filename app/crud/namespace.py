from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import edgedb

from app import errors
from app.entities import Namespace

from . import user

if TYPE_CHECKING:
    from app.typedefs import DBAnyConn, StrOrPath, StrOrUUID


def from_db(obj: edgedb.Object) -> Namespace:
    return Namespace.construct(
        id=obj.id,
        path=Path(obj.path),
        owner=user.from_db(obj.owner),
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
        return from_db(await conn.query_required_single(query, path=str(path)))
    except edgedb.NoDataError as exc:
        msg = f"Namespace with path={path} does not exists"
        raise errors.NamespaceNotFound(msg) from exc


async def get_by_owner(conn: DBAnyConn, owner_id: StrOrUUID) -> Namespace:
    query = """
        SELECT
            Namespace {
                id, path, owner: { id, username, superuser }
            }
        FILTER
            .owner.id = <uuid>$owner_id
        LIMIT 1
    """
    try:
        return from_db(await conn.query_required_single(query, owner_id=owner_id))
    except edgedb.NoDataError as exc:
        msg = f"Namespace with owner_id={owner_id} does not exists"
        raise errors.NamespaceNotFound(msg) from exc
