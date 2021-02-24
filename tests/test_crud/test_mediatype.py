from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app import crud

if TYPE_CHECKING:
    from edgedb import AsyncIOConnection

pytestmark = [pytest.mark.asyncio]


async def test_create_batch(db_conn: AsyncIOConnection):
    names = ["text/plain", "text/html"]
    await crud.mediatype.create_batch(db_conn, names)

    mediatypes = await db_conn.query("""
        SELECT
            MediaType { name }
        FILTER
            .name IN array_unpack(<array<str>>$names)
        ORDER BY .name
    """, names=names)

    assert mediatypes[0].name == "text/html"
    assert mediatypes[1].name == "text/plain"
