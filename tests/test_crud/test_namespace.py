from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app import crud, errors

if TYPE_CHECKING:
    from app.entities import User
    from app.typedefs import DBPool


pytestmark = [pytest.mark.asyncio]


async def test_get(db_pool: DBPool, user: User):
    namespace = await crud.namespace.get(db_pool, user.namespace.path)
    assert namespace.path == user.namespace.path


async def test_get_but_namespace_not_found(db_pool: DBPool):
    with pytest.raises(errors.NamespaceNotFound):
        await crud.namespace.get(db_pool, "user")
