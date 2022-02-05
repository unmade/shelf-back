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


async def create(conn: DBAnyConn, path: StrOrPath, owner_id: StrOrUUID) -> Namespace:
    """
    Create a namespace.

    Args:
        conn (DBAnyConn): A database connection.
        path (StrOrPath): Namespace path.
        owner_id (StrOrUUID): Namespace owner ID.

    Returns:
        Namespace: A freshly created namespa instance.
    """
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
        ) { id, path, owner: { id, username, superuser } }
    """

    return from_db(
        await conn.query_required_single(query, path=str(path), owner_id=owner_id)
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
        raise errors.NamespaceNotFound() from exc


async def get_by_owner(conn: DBAnyConn, owner_id: StrOrUUID) -> Namespace:
    query = """
        SELECT
            Namespace {
                id, path, owner: { id, username, superuser }
            }
        FILTER
            .owner.id = <uuid>$owner_id
    """
    try:
        return from_db(await conn.query_required_single(query, owner_id=owner_id))
    except edgedb.NoDataError as exc:
        raise errors.NamespaceNotFound() from exc
