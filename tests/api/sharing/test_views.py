from __future__ import annotations

import os.path
import urllib.parse
import uuid
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app.api.files.exceptions import PathNotFound
from app.api.sharing.exceptions import SharedLinkNotFound
from app.app.files.domain import File, SharedLink

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from app.app.files.domain import Namespace
    from tests.api.conftest import TestClient

pytestmark = [pytest.mark.asyncio]


def _make_file(ns_path: str, path: str) -> File:
    return File(
        id=uuid.uuid4(),
        ns_path=ns_path,
        name=os.path.basename(path),
        path=path,
        size=10,
        mediatype="plain/text",
    )


def _make_sharing_link() -> SharedLink:
    return SharedLink(
        id=uuid.uuid4(),
        file_id=str(uuid.uuid4()),
        token=uuid.uuid4().hex,
    )


class TestCreateSharedLink:
    url = "/sharing/create_shared_link"

    async def test(
        self,
        client: TestClient,
        namespace: Namespace,
        sharing_manager: MagicMock,
    ):
        # GIVEN
        ns_path = str(namespace.path)
        sharing_manager.create_link.return_value = _make_sharing_link()
        payload = {"path": "f.txt"}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert "token" in response.json()
        assert response.status_code == 200
        sharing_manager.create_link.assert_awaited_once_with(ns_path, "f.txt")

    async def test_when_file_not_found(
        self, client: TestClient, namespace: Namespace, sharing_manager: MagicMock
    ):
        # GIVEN
        sharing_manager.create_link.side_effect = File.NotFound
        payload = {"path": "im.jpeg"}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() == PathNotFound(path="im.jpeg").as_dict()
        assert response.status_code == 404


class TestGetSharedLink:
    url = "/sharing/get_shared_link"

    async def test(
        self,
        client: TestClient,
        namespace: Namespace,
        sharing_manager: MagicMock,
    ):
        # GIVEN
        ns_path = str(namespace.path)
        sharing_manager.get_link.return_value = _make_sharing_link()
        payload = {"path": "f.txt"}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert "token" in response.json()
        assert response.status_code == 200
        sharing_manager.get_link.assert_awaited_once_with(ns_path, "f.txt")

    async def test_when_link_not_found(
        self, client: TestClient, namespace: Namespace, sharing_manager: MagicMock
    ):
        # GIVEN
        sharing_manager.get_link.side_effect = File.NotFound
        payload = {"path": "im.jpeg"}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() == SharedLinkNotFound().as_dict()
        assert response.status_code == 404

    async def test_when_file_not_found(
        self, client: TestClient, namespace: Namespace, sharing_manager: MagicMock
    ):
        # GIVEN
        sharing_manager.get_link.side_effect = SharedLink.NotFound
        payload = {"path": "im.jpeg"}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() == SharedLinkNotFound().as_dict()
        assert response.status_code == 404


class TestGetSharedLinkDownloadUrl:
    url = "/sharing/get_shared_link_download_url"

    @mock.patch("app.api.shortcuts.create_download_cache")
    async def test(
        self,
        download_cache_mock,
        client: TestClient,
        sharing_manager: MagicMock,
    ):
        # GIVEN
        download_key = uuid.uuid4().hex
        download_cache_mock.return_value = download_key
        payload = {"token": "link-token", "filename": "f.txt"}

        # WHEN
        response = await client.post(self.url, json=payload)

        # THEN
        download_url = response.json()["download_url"]
        assert download_url.startswith(str(client.base_url))
        assert response.status_code == 200

        parts = urllib.parse.urlsplit(download_url)
        qs = urllib.parse.parse_qs(parts.query)
        assert qs["key"] == [download_key]

        sharing_manager.get_shared_item.assert_awaited_once_with("link-token")
        file = sharing_manager.get_shared_item.return_value
        download_cache_mock.assert_awaited_once_with(file.ns_path, file.path)

    async def test_when_link_not_found(
        self, client: TestClient, sharing_manager: MagicMock
    ):
        # GIVEN
        sharing_manager.get_shared_item.side_effect = SharedLink.NotFound
        payload = {"token": "link-token", "filename": "f.txt"}
        # WHEN
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() == SharedLinkNotFound().as_dict()
        assert response.status_code == 404
        sharing_manager.get_shared_item.assert_awaited_once_with(payload["token"])


class TestGetSharedLinkFile:
    url = "/sharing/get_shared_link_file"

    async def test(self, client: TestClient, sharing_manager: MagicMock):
        # GIVEN
        ns_path, token, filename = "admin", "link-token", "f.txt"
        file = _make_file(ns_path, filename)
        sharing_manager.get_shared_item.return_value = file
        payload = {"token": token, "filename": filename}
        # WHEN
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json()["id"] == file.id
        assert response.status_code == 200
        sharing_manager.get_shared_item.assert_awaited_once_with(payload["token"])

    async def test_when_link_not_found(
        self, client: TestClient, sharing_manager: MagicMock
    ):
        # GIVEN
        sharing_manager.get_shared_item.side_effect = SharedLink.NotFound
        payload = {"token": "link-token", "filename": "f.txt"}
        # WHEN
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() == SharedLinkNotFound().as_dict()
        assert response.status_code == 404
        sharing_manager.get_shared_item.assert_awaited_once_with(payload["token"])


class TestGetSharedLinkThumbnail:
    @staticmethod
    def url(token: str, size: str = "xs"):
        return f"/sharing/get_shared_link_thumbnail/{token}?size={size}"

    @pytest.mark.parametrize(["name", "size"], [("im.jpeg", "xs"), ("изо.jpeg", "lg")])
    async def test(
        self,
        client: TestClient,
        sharing_manager: MagicMock,
        name: str,
        size: str,
    ):
        # GIVEN
        ns_path, path, token = "admin", "f.txt", "link-token"
        file = _make_file(ns_path, path)
        sharing_manager.get_link_thumbnail.return_value = file, b"content"
        # WHEN
        response = await client.get(self.url(token=token, size=size))
        # THEN
        assert response.content
        headers = response.headers
        filename = f"thumbnail-{size}.webp"
        assert headers["Content-Disposition"] == f'inline; filename="{filename}"'
        assert int(headers["Content-Length"]) == 7
        assert headers["Content-Type"] == "image/webp"
        assert headers["Cache-Control"] == "private, max-age=31536000, no-transform"

    async def test_when_link_not_found(
        self, client: TestClient, sharing_manager: MagicMock
    ):
        # GIVEN
        token = "link-token"
        sharing_manager.get_link_thumbnail.side_effect = SharedLink.NotFound
        # WHEN
        response = await client.get(self.url(token=token))
        # THEN
        assert response.json() == SharedLinkNotFound().as_dict()
        assert response.status_code == 404


class TestRevokeSharedLink:
    async def test(
        self,
        client: TestClient,
        namespace: Namespace,
        sharing_manager: MagicMock,
    ):
        # GIVEN
        token, filename = "link-token", "f.txt"
        # WHEN
        payload = {"token": token, "filename": filename}
        client.mock_namespace(namespace)
        # THEN
        response = await client.post("/sharing/revoke_shared_link", json=payload)
        assert response.status_code == 200
        sharing_manager.revoke_link.assert_awaited_once_with(token)
