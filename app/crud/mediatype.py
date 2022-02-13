from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from app.typedefs import DBAnyConn


async def create_missing(conn: DBAnyConn, names: Iterable[str]) -> None:
    """
    Create all media types that do not exist in the database.

    Args:
        conn (DBAnyConn): Database connection.
        names (Iterable[str]): Media types names to create.
    """
    query = """
        WITH
            mediatypes := {DISTINCT array_unpack(<array<str>>$names)},
            missing := (
                SELECT
                    mediatypes
                FILTER
                    mediatypes NOT IN (SELECT MediaType { name }).name
            )
        FOR name in {missing}
        UNION (
            INSERT MediaType {
                name := name
            }
        )
    """

    await conn.query(query, names=list(names))
