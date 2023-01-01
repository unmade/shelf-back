from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

import pytest

from app.api.files.exceptions import PathNotFound
from app.api.sharing.exceptions import SharedLinkNotFound
from app.cache import cache

if TYPE_CHECKING:
    from io import BytesIO

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
        assert len(response.json()["token"]) > 16
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
        assert len(response.json()["token"]) > 16
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


class TestGetSharedLinkFile:
    async def test(
        self,
        client: TestClient,
        namespace: Namespace,
        file_factory: FileFactory,
    ):
        file = await file_factory(namespace.path)
        token = secrets.token_hex()
        await cache.set(token, f"{namespace.path}:{file.path}")
        payload = {"token": token, "filename": file.name}
        response = await client.post("/sharing/get_shared_link_file", json=payload)
        assert response.json()["id"] == file.id
        assert response.json()["thumbnail_url"] is None
        assert response.status_code == 200

    async def test_image_file(
        self,
        client: TestClient,
        namespace: Namespace,
        file_factory: FileFactory,
        image_content: BytesIO,
    ):
        file = await file_factory(namespace.path, "im.jpeg", content=image_content)
        token = secrets.token_hex()
        await cache.set(token, f"{namespace.path}:{file.path}")
        expected_thumbnail_url = f"/get_shared_link_thumbnail/{token}"
        payload = {"token": token, "filename": file.name}
        response = await client.post("/sharing/get_shared_link_file", json=payload)
        assert response.json()["id"] == file.id
        assert response.json()["thumbnail_url"].endswith(expected_thumbnail_url)
        assert response.status_code == 200

    async def test_but_link_does_not_exist(
        self,
        client: TestClient,
        namespace: Namespace,
        file_factory: FileFactory,
    ):
        file = await file_factory(namespace.path, "im.jpeg")
        token = secrets.token_hex()
        payload = {"token": token, "filename": file.name}
        response = await client.post("/sharing/get_shared_link_file", json=payload)
        assert response.json() == SharedLinkNotFound().as_dict()
        assert response.status_code == 404

    async def test_but_file_does_not_exist(
        self,
        client: TestClient,
        namespace: Namespace,
    ):
        token = secrets.token_hex()
        await cache.set(token, f"{namespace.path}:f.txt")
        payload = {"token": token, "filename": "f.txt"}
        response = await client.post("/sharing/get_shared_link_file", json=payload)
        assert response.json() == PathNotFound(path="f.txt").as_dict()
        assert response.status_code == 404
