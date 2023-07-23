from __future__ import annotations

import urllib.parse
import uuid
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app.api.exceptions import UserNotFound
from app.api.files.exceptions import PathNotFound
from app.api.sharing.exceptions import FileMemberAlreadyExists, SharedLinkNotFound
from app.api.sharing.schemas import FileMemberAccessLevel
from app.app.files.domain import File, FileMember, Path, SharedLink
from app.app.users.domain import User

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from app.app.files.domain import AnyPath, Namespace
    from tests.api.conftest import TestClient

pytestmark = [pytest.mark.asyncio]


def _make_file(ns_path: str, path: AnyPath) -> File:
    return File(
        id=uuid.uuid4(),
        ns_path=ns_path,
        name=Path(path).name,
        path=path,
        size=10,
        mediatype="plain/text",
    )


def _make_file_member(file: File, user: User) -> FileMember:
    return FileMember(
        file_id=file.id,
        actions=FileMember.EDITOR,
        user=FileMember.User(
            id=user.id,
            username=user.username,
        ),
    )


def _make_sharing_link() -> SharedLink:
    return SharedLink(
        id=uuid.uuid4(),
        file_id=str(uuid.uuid4()),
        token=uuid.uuid4().hex,
    )


def _make_user(username: str) -> User:
    return User(
        id=uuid.uuid4(),
        username=username,
        password="root",
    )


class TestAddMember:
    url = "/sharing/add_member"

    async def test(
        self,
        client: TestClient,
        namespace: Namespace,
        sharing_use_case: MagicMock,
    ):
        # GIVEN
        file, user = _make_file(namespace.path, "f.txt"), _make_user("user")
        file_member = _make_file_member(file, user)
        sharing_use_case.add_member.return_value = file_member
        payload = {"file_id": file.id, "username": user.username}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json()["id"] == str(user.id)
        assert response.status_code == 200
        sharing_use_case.add_member.assert_awaited_once_with(
            namespace.path, file.id, user.username
        )

    async def test_when_file_does_not_exist(
        self,
        client: TestClient,
        namespace: Namespace,
        sharing_use_case: MagicMock,
    ):
        # GIVEN
        ns_path = str(namespace.path)
        file_id, username = str(uuid.uuid4()), "user"
        sharing_use_case.add_member.side_effect = File.NotFound()
        payload = {"file_id": file_id, "username": username}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() == PathNotFound(path=file_id).as_dict()
        assert response.status_code == 404
        sharing_use_case.add_member.assert_awaited_once_with(ns_path, file_id, username)

    async def test_when_file_member_already_exists(
        self,
        client: TestClient,
        namespace: Namespace,
        sharing_use_case: MagicMock,
    ):
        # GIVEN
        ns_path = str(namespace.path)
        file_id, username = str(uuid.uuid4()), "user"
        sharing_use_case.add_member.side_effect = FileMember.AlreadyExists()
        payload = {"file_id": file_id, "username": username}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() == FileMemberAlreadyExists().as_dict()
        assert response.status_code == 400
        sharing_use_case.add_member.assert_awaited_once_with(ns_path, file_id, username)

    async def test_when_user_does_not_exist(
        self,
        client: TestClient,
        namespace: Namespace,
        sharing_use_case: MagicMock,
    ):
        # GIVEN
        ns_path = str(namespace.path)
        file_id, username = str(uuid.uuid4()), "user"
        sharing_use_case.add_member.side_effect = User.NotFound()
        payload = {"file_id": file_id, "username": username}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() == UserNotFound().as_dict()
        assert response.status_code == 404
        sharing_use_case.add_member.assert_awaited_once_with(ns_path, file_id, username)


class TestCreateSharedLink:
    url = "/sharing/create_shared_link"

    async def test(
        self,
        client: TestClient,
        namespace: Namespace,
        sharing_use_case: MagicMock,
    ):
        # GIVEN
        ns_path = str(namespace.path)
        sharing_use_case.create_link.return_value = _make_sharing_link()
        payload = {"path": "f.txt"}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert "token" in response.json()
        assert response.status_code == 200
        sharing_use_case.create_link.assert_awaited_once_with(ns_path, "f.txt")

    async def test_when_file_not_found(
        self, client: TestClient, namespace: Namespace, sharing_use_case: MagicMock
    ):
        # GIVEN
        sharing_use_case.create_link.side_effect = File.NotFound
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
        sharing_use_case: MagicMock,
    ):
        # GIVEN
        ns_path = str(namespace.path)
        sharing_use_case.get_link.return_value = _make_sharing_link()
        payload = {"path": "f.txt"}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert "token" in response.json()
        assert response.status_code == 200
        sharing_use_case.get_link.assert_awaited_once_with(ns_path, "f.txt")

    async def test_when_link_not_found(
        self, client: TestClient, namespace: Namespace, sharing_use_case: MagicMock
    ):
        # GIVEN
        sharing_use_case.get_link.side_effect = File.NotFound
        payload = {"path": "im.jpeg"}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() == SharedLinkNotFound().as_dict()
        assert response.status_code == 404

    async def test_when_file_not_found(
        self, client: TestClient, namespace: Namespace, sharing_use_case: MagicMock
    ):
        # GIVEN
        sharing_use_case.get_link.side_effect = SharedLink.NotFound
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
        sharing_use_case: MagicMock,
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

        sharing_use_case.get_shared_item.assert_awaited_once_with("link-token")
        file = sharing_use_case.get_shared_item.return_value
        download_cache_mock.assert_awaited_once_with(file.ns_path, file.path)

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
        assert response.json()["id"] == file.id
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
        sharing_use_case.get_link_thumbnail.return_value = file, b"content"
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


class TestListMembers:
    url = "/sharing/list_members"

    async def test(
        self,
        client: TestClient,
        namespace: Namespace,
        sharing_use_case: MagicMock,
    ):
        # GIVEN
        file = _make_file(namespace.path, "f.txt")
        users = [_make_user("user_a"), _make_user("user_b")]
        members = [_make_file_member(file, user) for user in users]
        sharing_use_case.list_members.return_value = members
        payload = {"id": file.id}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert len(response.json()["members"]) == 2
        assert response.status_code == 200
        sharing_use_case.list_members.assert_awaited_once_with(namespace.path, file.id)

    async def test_when_file_not_found(
        self,
        client: TestClient,
        namespace: Namespace,
        sharing_use_case: MagicMock,
    ):
        # GIVEN
        file_id = str(uuid.uuid4())
        sharing_use_case.list_members.side_effect = File.NotFound
        payload = {"id": file_id}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() == PathNotFound(path=file_id).as_dict()
        assert response.status_code == 404
        sharing_use_case.list_members.assert_awaited_once_with(namespace.path, file_id)


class TestRemoveMember:
    url = "/sharing/remove_member"

    async def test(
        self,
        client: TestClient,
        namespace: Namespace,
        sharing_use_case: MagicMock,
    ):
        # GIVEN
        file_id, member_id = str(uuid.uuid4()), uuid.uuid4()
        payload = {"file_id": file_id, "member_id": str(member_id)}
        client.mock_namespace(namespace)
        # WHEN
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.status_code == 200
        sharing_use_case.remove_member.assert_awaited_once_with(file_id, member_id)

    async def test_when_file_not_found(
        self,
        client: TestClient,
        namespace: Namespace,
        sharing_use_case: MagicMock,
    ):
        # GIVEN
        file_id, member_id = str(uuid.uuid4()), uuid.uuid4()
        payload = {"file_id": file_id, "member_id": str(member_id)}
        sharing_use_case.remove_member.side_effect = File.NotFound
        client.mock_namespace(namespace)
        # WHEN
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() == PathNotFound(path=str(file_id)).as_dict()
        assert response.status_code == 404
        sharing_use_case.remove_member.assert_awaited_once_with(file_id, member_id)


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


class TestSetMemberAccessLevel:
    url = "/sharing/set_member_access_level"

    async def test(
        self,
        client: TestClient,
        namespace: Namespace,
        sharing_use_case: MagicMock,
    ):
        # GIVEN
        file_id, member_id = str(uuid.uuid4()), uuid.uuid4()
        access_level = FileMemberAccessLevel.viewer
        payload = {
            "file_id": file_id,
            "member_id": str(member_id),
            "access_level": access_level,
        }
        client.mock_namespace(namespace)
        # WHEN
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.status_code == 200
        sharing_use_case.set_member_actions.assert_awaited_once_with(
            file_id,
            member_id,
            actions=FileMember.VIEWER,
        )
