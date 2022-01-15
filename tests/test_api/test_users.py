from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.api.users.exceptions import FileNotFound

if TYPE_CHECKING:
    from app.entities import Namespace
    from tests.conftest import TestClient
    from tests.factories import FileFactory, NamespaceFactory

pytestmark = [pytest.mark.asyncio, pytest.mark.database(transaction=True)]


async def test_add_bookmark(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path)
    payload = {"id": str(file.id)}
    user_id = namespace.owner.id
    response = await client.login(user_id).post("/users/bookmarks/add", json=payload)
    assert response.json() is None
    assert response.status_code == 200


async def test_add_bookmark_but_file_does_not_exist(
    client: TestClient,
    namespace: Namespace,
):
    user_id = namespace.owner.id
    payload = {"id": str(uuid.uuid4())}
    response = await client.login(user_id).post("/users/bookmarks/add", json=payload)
    assert response.json() == FileNotFound().as_dict()
    assert response.status_code == 404


async def test_add_bookmark_but_file_from_another_namespace(
    client: TestClient,
    namespace_factory: NamespaceFactory,
    file_factory: FileFactory,
):
    namespace_a = await namespace_factory()
    namespace_b = await namespace_factory()
    file = await file_factory(namespace_b.path)
    user_id = namespace_a.owner.id
    payload = {"id": str(file.id)}
    response = await client.login(user_id).post("/users/bookmarks/add", json=payload)
    assert response.json() == FileNotFound().as_dict()
    assert response.status_code == 404
