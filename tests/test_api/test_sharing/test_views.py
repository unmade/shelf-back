from __future__ import annotations

import secrets
import urllib.parse
from typing import TYPE_CHECKING

import pytest

from app.api.files.exceptions import IsADirectory, PathNotFound, ThumbnailUnavailable
from app.api.sharing.exceptions import SharedLinkNotFound
from app.cache import cache

if TYPE_CHECKING:
    from io import BytesIO

    from app.entities import Namespace
    from tests.conftest import TestClient
    from tests.factories import FileFactory, FolderFactory

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

    async def test_but_file_not_found(self, client: TestClient, namespace: Namespace):
        payload = {"path": "im.jpeg"}
        client.login(namespace.owner.id)
        response = await client.post("/sharing/create_shared_link", json=payload)
        assert response.json() == PathNotFound(path="im.jpeg").as_dict()
        assert response.status_code == 404


class TestGetSharedLinkDownloadUrl:
    url = "/sharing/get_shared_link_download_url"

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

    async def test_but_file_not_found(self, client: TestClient, namespace: Namespace):
        token = secrets.token_hex()
        await cache.set(token, f"{namespace.path}:f.txt")
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

    async def test_but_file_not_found(self, client: TestClient, namespace: Namespace):
        token = secrets.token_hex()
        await cache.set(token, f"{namespace.path}:f.txt")
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
        name: str,
        size: str,
    ):
        file = await file_factory(namespace.path, path=name, content=image_content)
        token = secrets.token_hex()
        await cache.set(token, f"{namespace.path}:{file.path}")
        response = await client.get(self.url(token=token, size=size))
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

    async def test_but_file_not_found(self, client: TestClient, namespace: Namespace):
        token = secrets.token_hex()
        await cache.set(token, f"{namespace.path}:f.txt")
        response = await client.get(self.url(token=token))
        assert response.json() == SharedLinkNotFound().as_dict()

    async def test_but_it_is_a_folder(
        self,
        client: TestClient,
        namespace: Namespace,
        folder_factory: FolderFactory,
    ):
        folder = await folder_factory(namespace.path)
        token = secrets.token_hex()
        await cache.set(token, f"{namespace.path}:{folder.path}")
        client.login(namespace.owner.id)
        response = await client.get(self.url(token=token))
        assert response.json() == IsADirectory(path=folder.id).as_dict()

    async def test_but_shared_link_is_not_thumbnailable(
        self,
        client: TestClient,
        namespace: Namespace,
        file_factory: FileFactory,
    ):
        file = await file_factory(namespace.path)
        token = secrets.token_hex()
        await cache.set(token, f"{namespace.path}:{file.path}")
        client.login(namespace.owner.id)
        response = await client.get(self.url(token=token))
        assert response.json() == ThumbnailUnavailable(path=file.id).as_dict()
