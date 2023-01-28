from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app import crud, errors

if TYPE_CHECKING:
    from app.entities import Namespace, User
    from app.typedefs import DBTransaction


pytestmark = [pytest.mark.asyncio, pytest.mark.database]


async def test_create(tx: DBTransaction, user: User):
    namespace = await crud.namespace.create(tx, user.username, user.id)
    assert str(namespace.path) == user.username
    assert namespace.owner == user


async def test_get(tx: DBTransaction, namespace: Namespace):
    assert await crud.namespace.get(tx, namespace.path) == namespace


async def test_get_but_namespace_not_found(tx: DBTransaction):
    with pytest.raises(errors.NamespaceNotFound) as excinfo:
        await crud.namespace.get(tx, "user")

    msg = "Namespace with path=user does not exists"
    assert str(excinfo.value) == msg


async def test_get_by_owner(tx: DBTransaction, namespace: Namespace):
    assert await crud.namespace.get_by_owner(tx, namespace.owner.id) == namespace


async def test_get_by_owner_but_namespace_not_found(tx: DBTransaction):
    owner_id = uuid.uuid4()
    with pytest.raises(errors.NamespaceNotFound) as excinfo:
        await crud.namespace.get_by_owner(tx, owner_id)

    msg = f"Namespace with owner_id={owner_id} does not exists"
    assert str(excinfo.value) == msg
