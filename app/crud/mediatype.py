from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from edgedb import AsyncIOConnection


async def create_batch(conn: AsyncIOConnection, names: Iterable[str]) -> None:
    """
    Create media types with specified names. If name already exists, do nothing.

    Args:
        conn (AsyncIOConnection): Database connection.
        names (Iterable[str]): Media type names.
    """
    await conn.query("""
        FOR name in {array_unpack(<array<str>>$names)}
        UNION (
            INSERT MediaType {
                name := name,
            }
            UNLESS CONFLICT ON .name
        );
    """, names=list(names))
