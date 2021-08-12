from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app import crud, errors

if TYPE_CHECKING:
    from app.entities import Namespace
    from app.typedefs import DBTransaction


pytestmark = [pytest.mark.asyncio, pytest.mark.database]


async def test_get(tx: DBTransaction, namespace: Namespace):
    namespace = await crud.namespace.get(tx, namespace.path)
    assert namespace.path == namespace.path


async def test_get_but_namespace_not_found(tx: DBTransaction):
    with pytest.raises(errors.NamespaceNotFound):
        await crud.namespace.get(tx, "user")
