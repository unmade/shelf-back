from __future__ import annotations

from typing import TYPE_CHECKING

import edgedb

from app import errors
from app.entities import Namespace

if TYPE_CHECKING:
    from app.typedefs import DBAnyConn, StrOrPath


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
                id, path
            }
        FILTER
            .path = <str>$path
    """

    try:
        return Namespace.from_orm(await conn.query_one(query, path=str(path)))
    except edgedb.NoDataError as exc:
        raise errors.NamespaceNotFound() from exc
