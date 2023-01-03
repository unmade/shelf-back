from __future__ import annotations

import secrets
import urllib.parse
from typing import TYPE_CHECKING

import pytest

from app.api.files.exceptions import PathNotFound
from app.api.sharing.exceptions import SharedLinkNotFound
from app.cache import cache

if TYPE_CHECKING:
    from io import BytesIO

    from app.entities import Namespace
    from tests.conftest import TestClient
    from tests.factories import FileFactory, SharedLinkFactory

pytestmark = [pytest.mark.asyncio, pytest.mark.database(transaction=True)]


class TestCreateSharedLink:
    async def test(
        self,
        client: TestClient,
        namespace: Namespace,
        file_factory: FileFactory,
    ):
        file = await file_factory(namespace.path)
        payload = {"path": file.path}
        client.login(namespace.owner.id)
        response = await client.post("/sharing/create_shared_link", json=payload)
        assert "token" in response.json()
        assert response.status_code == 200

    async def test_but_file_not_found(self, client: TestClient, namespace: Namespace):
        payload = {"path": "im.jpeg"}
        client.login(namespace.owner.id)
        response = await client.post("/sharing/create_shared_link", json=payload)
        assert response.json() == PathNotFound(path="im.jpeg").as_dict()
        assert response.status_code == 404


class TestGetSharedLink:
    async def test(
        self,
        client: TestClient,
        namespace: Namespace,
        file_factory: FileFactory,
        shared_link_factory: SharedLinkFactory,
    ):
        file = await file_factory(namespace.path)
        await shared_link_factory(file.id)
        payload = {"path": file.path}
        client.login(namespace.owner.id)
        response = await client.post("/sharing/get_shared_link", json=payload)
        assert "token" in response.json()
        assert response.status_code == 200

    async def test_but_link_not_found(self, client: TestClient, namespace: Namespace):
        payload = {"path": "f.txt"}
        client.login(namespace.owner.id)
        response = await client.post("/sharing/get_shared_link", json=payload)
        assert response.json() == SharedLinkNotFound().as_dict()
        assert response.status_code == 404


class TestGetSharedLinkDownloadUrl:
    url = "/sharing/get_shared_link_download_url"

    async def test(
        self,
        client: TestClient,
        namespace: Namespace,
        file_factory: FileFactory,
        shared_link_factory: SharedLinkFactory,
    ):
        file = await file_factory(namespace.path)
        link = await shared_link_factory(file.id)
        payload = {"token": link.token, "filename": file.name}
        response = await client.post(self.url, json=payload)
        download_url = response.json()["download_url"]
        assert download_url.startswith(str(client.base_url))
        assert response.status_code == 200
        parts = urllib.parse.urlsplit(download_url)
        qs = urllib.parse.parse_qs(parts.query)
        assert len(qs["key"]) == 1
        value = await cache.get(qs["key"][0])
        assert value == f"{namespace.path}:{file.path}"

    async def test_but_link_not_found(self, client: TestClient):
        token = secrets.token_hex()
        payload = {"token": token, "filename": "f.txt"}
        response = await client.post(self.url, json=payload)
        assert response.json() == SharedLinkNotFound().as_dict()
        assert response.status_code == 404


class TestGetSharedLinkFile:
    async def test(
        self,
        client: TestClient,
        namespace: Namespace,
        file_factory: FileFactory,
        shared_link_factory: SharedLinkFactory,
    ):
        file = await file_factory(namespace.path)
        link = await shared_link_factory(file.id)
        payload = {"token": link.token, "filename": file.name}
        response = await client.post("/sharing/get_shared_link_file", json=payload)
        assert response.json()["id"] == file.id
        assert response.json()["thumbnail_url"] is None
        assert response.status_code == 200

    async def test_image_file(
        self,
        client: TestClient,
        namespace: Namespace,
        file_factory: FileFactory,
        shared_link_factory: SharedLinkFactory,
        image_content: BytesIO,
    ):
        file = await file_factory(namespace.path, "im.jpeg", content=image_content)
        link = await shared_link_factory(file.id)
        expected_thumbnail_url = f"/get_shared_link_thumbnail/{link.token}"
        payload = {"token": link.token, "filename": file.name}
        response = await client.post("/sharing/get_shared_link_file", json=payload)
        assert response.json()["id"] == file.id
        thumbnail_url = response.json()["thumbnail_url"]
        assert thumbnail_url.startswith(str(client.base_url))
        assert thumbnail_url.endswith(expected_thumbnail_url)
        assert response.status_code == 200

    async def test_but_link_not_found(self, client: TestClient):
        token = secrets.token_hex()
        payload = {"token": token, "filename": "f.txt"}
        response = await client.post("/sharing/get_shared_link_file", json=payload)
        assert response.json() == SharedLinkNotFound().as_dict()
        assert response.status_code == 404


class TestGetSharedLinkThumbnail:
    @staticmethod
    def url(token: str, size: str = "xs"):
        return f"/sharing/get_shared_link_thumbnail/{token}?size={size}"

    @pytest.mark.parametrize(["name", "size"], [("im.jpeg", "xs"), ("изо.jpeg", "lg")])
    async def test(
        self,
        client: TestClient,
        namespace: Namespace,
        image_content: BytesIO,
        file_factory: FileFactory,
        shared_link_factory: SharedLinkFactory,
        name: str,
        size: str,
    ):
        file = await file_factory(namespace.path, path=name, content=image_content)
        link = await shared_link_factory(file.id)
        response = await client.get(self.url(token=link.token, size=size))
        assert response.content
        headers = response.headers
        filename = f"thumbnail-{size}.webp"
        assert headers["Content-Disposition"] == f'inline; filename="{filename}"'
        assert int(headers["Content-Length"]) < file.size
        assert headers["Content-Type"] == "image/webp"
        assert headers["Cache-Control"] == "private, max-age=31536000, no-transform"

    async def test_but_link_not_found(self, client: TestClient):
        token = secrets.token_hex()
        response = await client.get(self.url(token=token))
        assert response.json() == SharedLinkNotFound().as_dict()
        assert response.status_code == 404


class TestRevokeSharedLink:
    async def test(
        self,
        client: TestClient,
        namespace: Namespace,
        file_factory: FileFactory,
        shared_link_factory: SharedLinkFactory,
    ):
        file = await file_factory(namespace.path)
        link = await shared_link_factory(file.id)
        payload = {"token": link.token, "filename": file.name}
        client.login(namespace.owner.id)
        response = await client.post("/sharing/revoke_shared_link", json=payload)
        assert response.status_code == 200
