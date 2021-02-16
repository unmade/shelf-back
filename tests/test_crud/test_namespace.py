from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app import crud, errors

if TYPE_CHECKING:
    from edgedb import AsyncIOConnection
    from app.entities import User


pytestmark = [pytest.mark.asyncio]


async def test_get(db_conn: AsyncIOConnection, user: User):
    namespace = await crud.namespace.get(db_conn, user.namespace.path)
    assert namespace.path == user.namespace.path


async def test_get_but_namespace_not_found(db_conn: AsyncIOConnection):
    with pytest.raises(errors.NamespaceNotFound):
        await crud.namespace.get(db_conn, "user")
