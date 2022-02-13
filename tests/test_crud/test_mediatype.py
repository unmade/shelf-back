from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app import crud

if TYPE_CHECKING:
    from app.typedefs import DBTransaction
    from tests.factories import MediaTypeFactory

pytestmark = [pytest.mark.asyncio, pytest.mark.database]


async def test_create_missing(tx: DBTransaction, mediatype_factory: MediaTypeFactory):
    await mediatype_factory("image/jpeg")
    await mediatype_factory("image/png")

    names = ["image/jpeg", "image/png", "text/plain", "text/plain", "text/csv"]
    await crud.mediatype.create_missing(tx, names=names)

    mediatypes_in_db = await tx.query("SELECT MediaType { name } ORDER BY .name")
    assert [item.name for item in mediatypes_in_db] == sorted(set(names))
