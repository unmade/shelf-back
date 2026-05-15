from __future__ import annotations

import urllib.parse
import uuid
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app.api.files.exceptions import FileActionNotAllowed, PathNotFound
from app.api.sharing.exceptions import SharedLinkNotFound
from app.app.files.domain import File, Path, SharedLink
from app.toolkit.mediatypes import MediaType

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from app.api.exceptions import APIError
    from app.app.files.domain import AnyPath, Namespace
    from tests.api.conftest import TestClient

pytestmark = [pytest.mark.anyio]

_FILE_ID = uuid.uuid4()


def _make_file(ns_path: str, path: AnyPath, mediatype: str = "plain/text") -> File:
    return File(
        id=uuid.uuid7(),
        owner_id=uuid.uuid7(),
        ns_path=ns_path,
        name=Path(path).name,
        path=Path(path),
        chash=uuid.uuid4().hex,
        size=10,
        mediatype=mediatype,
    )


def _make_sharing_link() -> SharedLink:
    return SharedLink(
        id=uuid.uuid4(),
        file_id=uuid.uuid4(),
        token=uuid.uuid4().hex,
    )


class TestCreateSharedLink:
    url = "/sharing/create_shared_link"

    async def test(
        self,
        client: TestClient,
        namespace: Namespace,
        sharing_use_case: MagicMock,
    ):
        # GIVEN
        ns_path, file_id = str(namespace.path), uuid.uuid4()
        sharing_use_case.create_link.return_value = _make_sharing_link()
        payload = {"file_id": str(file_id)}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert "token" in response.json()
        assert response.status_code == 200
        sharing_use_case.create_link.assert_awaited_once_with(ns_path, file_id)

    @pytest.mark.parametrize(["error", "expected_error"], [
        (File.ActionNotAllowed(), FileActionNotAllowed()),
        (File.NotFound(), PathNotFound(path=str(_FILE_ID))),
    ])
    async def test_reraising_app_errors_to_api_errors(
        self,
        client: TestClient,
        namespace: Namespace,
        sharing_use_case: MagicMock,
        error: Exception,
        expected_error: APIError,
    ):
        # GIVEN
        sharing_use_case.create_link.side_effect = error
        payload = {"file_id": str(_FILE_ID)}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() == expected_error.as_dict()
        assert response.status_code == expected_error.status_code


class TestGetSharedLink:
    url = "/sharing/get_shared_link"

    async def test(
        self,
        client: TestClient,
        namespace: Namespace,
        sharing_use_case: MagicMock,
    ):
        # GIVEN
        ns_path, file_id = str(namespace.path), uuid.uuid4()
        sharing_use_case.get_link.return_value = _make_sharing_link()
        payload = {"file_id": str(file_id)}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert "token" in response.json()
        assert response.status_code == 200
        sharing_use_case.get_link.assert_awaited_once_with(ns_path, file_id)

    @pytest.mark.parametrize(["error", "expected_error"], [
        (File.NotFound(), SharedLinkNotFound()),
        (SharedLink.NotFound(), SharedLinkNotFound()),
    ])
    async def test_reraising_app_errors_to_api_errors(
        self,
        client: TestClient,
        namespace: Namespace,
        sharing_use_case: MagicMock,
        error: Exception,
        expected_error: APIError,
    ):
        # GIVEN
        sharing_use_case.get_link.side_effect = error
        payload = {"file_id": str(_FILE_ID)}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() == expected_error.as_dict()
        assert response.status_code == expected_error.status_code


class TestGetSharedLinkDownloadUrl:
    url = "/sharing/get_shared_link_download_url"

    @mock.patch("app.api.shortcuts.create_download_cache")
    @pytest.mark.parametrize(["mediatype", "expected_path"], [
        (MediaType.TEXT_PLAIN, "/download?"),
        (MediaType.FOLDER, "/download_folder?"),
    ])
    async def test(
        self,
        download_cache_mock: MagicMock,
        client: TestClient,
        sharing_use_case: MagicMock,
        mediatype: MediaType,
        expected_path: str,
    ):
        # GIVEN
        file = _make_file("admin", "f", mediatype=mediatype)
        sharing_use_case.get_shared_item.return_value = file
        download_key = uuid.uuid4().hex
        download_cache_mock.return_value = download_key
        payload = {"token": "link-token", "filename": file.name}

        # WHEN
        response = await client.post(self.url, json=payload)

        # THEN
        download_url = response.json()["download_url"]
        assert download_url.startswith(str(client.base_url))
        assert expected_path in download_url
        assert response.status_code == 200

        parts = urllib.parse.urlsplit(download_url)
        qs = urllib.parse.parse_qs(parts.query)
        assert qs["key"] == [download_key]

        sharing_use_case.get_shared_item.assert_awaited_once_with("link-token")
        file = sharing_use_case.get_shared_item.return_value
        download_cache_mock.assert_awaited_once_with(file)

    async def test_when_link_not_found(
        self, client: TestClient, sharing_use_case: MagicMock
    ):
        # GIVEN
        sharing_use_case.get_shared_item.side_effect = SharedLink.NotFound
        payload = {"token": "link-token", "filename": "f.txt"}
        # WHEN
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() == SharedLinkNotFound().as_dict()
        assert response.status_code == 404
        sharing_use_case.get_shared_item.assert_awaited_once_with(payload["token"])


class TestGetSharedLinkFile:
    url = "/sharing/get_shared_link_file"

    async def test(self, client: TestClient, sharing_use_case: MagicMock):
        # GIVEN
        ns_path, token, filename = "admin", "link-token", "f.txt"
        file = _make_file(ns_path, filename)
        sharing_use_case.get_shared_item.return_value = file
        payload = {"token": token, "filename": filename}
        # WHEN
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json()["id"] == str(file.id)
        assert response.status_code == 200
        sharing_use_case.get_shared_item.assert_awaited_once_with(payload["token"])

    async def test_when_link_not_found(
        self, client: TestClient, sharing_use_case: MagicMock
    ):
        # GIVEN
        sharing_use_case.get_shared_item.side_effect = SharedLink.NotFound
        payload = {"token": "link-token", "filename": "f.txt"}
        # WHEN
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() == SharedLinkNotFound().as_dict()
        assert response.status_code == 404
        sharing_use_case.get_shared_item.assert_awaited_once_with(payload["token"])


class TestGetSharedLinkThumbnail:
    @staticmethod
    def url(token: str, size: str = "xs"):
        return f"/sharing/get_shared_link_thumbnail/{token}?size={size}"

    @pytest.mark.parametrize(["name", "size"], [("im.jpeg", "xs"), ("изо.jpeg", "lg")])
    async def test(
        self,
        client: TestClient,
        sharing_use_case: MagicMock,
        name: str,
        size: str,
    ):
        # GIVEN
        ns_path, path, token = "admin", "f.txt", "link-token"
        file = _make_file(ns_path, path)
        thumbnail, mediatype = b"content", MediaType.IMAGE_WEBP
        sharing_use_case.get_link_thumbnail.return_value = file, thumbnail, mediatype
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
        self, client: TestClient, sharing_use_case: MagicMock
    ):
        # GIVEN
        token = "link-token"
        sharing_use_case.get_link_thumbnail.side_effect = SharedLink.NotFound
        # WHEN
        response = await client.get(self.url(token=token))
        # THEN
        assert response.json() == SharedLinkNotFound().as_dict()
        assert response.status_code == 404


class TestListSharedLinks:
    url = "/sharing/list_shared_links"

    async def test(
        self,
        client: TestClient,
        namespace: Namespace,
        sharing_use_case: MagicMock,
    ):
        # GIVEN
        ns_path = str(namespace.path)
        links = [
            _make_sharing_link(),
            _make_sharing_link(),
        ]
        sharing_use_case.list_shared_links.return_value = links
        # WHEN
        client.mock_namespace(namespace)
        response = await client.get(self.url)
        # THEN
        items = response.json()["items"]
        assert len(items) == 2
        assert response.status_code == 200
        sharing_use_case.list_shared_links.assert_awaited_once_with(ns_path)


class TestRevokeSharedLink:
    async def test(
        self,
        client: TestClient,
        namespace: Namespace,
        sharing_use_case: MagicMock,
    ):
        # GIVEN
        token, filename = "link-token", "f.txt"
        payload = {"token": token, "filename": filename}
        client.mock_namespace(namespace)
        # WHEN
        response = await client.post("/sharing/revoke_shared_link", json=payload)
        # THEN
        assert response.status_code == 200
        sharing_use_case.revoke_link.assert_awaited_once_with(token)
