from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.api.files.exceptions import PathNotFound

if TYPE_CHECKING:
    from app.entities import Namespace
    from tests.conftest import TestClient
    from tests.factories import FileFactory

pytestmark = [pytest.mark.asyncio, pytest.mark.database(transaction=True)]


class TestCreateSharedLink:
    async def test_file(
        self,
        client: TestClient,
        namespace: Namespace,
        file_factory: FileFactory,
    ):
        file = await file_factory(namespace.path)
        payload = {"path": file.path}
        client.login(namespace.owner.id)
        response = await client.post("/sharing/create_shared_link", json=payload)
        assert len(response.json()["key"]) > 16
        assert response.status_code == 200

    async def test_folder(
        self,
        client: TestClient,
        namespace: Namespace,
        file_factory: FileFactory,
    ):
        await file_factory(namespace.path, "a/f.txt")
        payload = {"path": "a"}
        client.login(namespace.owner.id)
        response = await client.post("/sharing/create_shared_link", json=payload)
        assert len(response.json()["key"]) > 16
        assert response.status_code == 200

    async def test_but_file_not_found(
        self,
        client: TestClient,
        namespace: Namespace,
    ):
        payload = {"path": "im.jpeg"}
        client.login(namespace.owner.id)
        response = await client.post("/sharing/create_shared_link", json=payload)
        assert response.json() == PathNotFound(path="im.jpeg").as_dict()
        assert response.status_code == 404
