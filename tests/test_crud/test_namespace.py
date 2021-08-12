from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app import crud, errors

if TYPE_CHECKING:
    from app.entities import Namespace
    from app.typedefs import DBPool


pytestmark = [pytest.mark.asyncio]


async def test_get(db_pool: DBPool, namespace: Namespace):
    namespace = await crud.namespace.get(db_pool, namespace.path)
    assert namespace.path == namespace.path


async def test_get_but_namespace_not_found(db_pool: DBPool):
    with pytest.raises(errors.NamespaceNotFound):
        await crud.namespace.get(db_pool, "user")
