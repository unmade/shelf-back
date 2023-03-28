from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.api.users.exceptions import FileNotFound
from app.app.files.domain import File
from app.app.users.domain import Bookmark

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from app.app.files.domain import Namespace
    from app.app.users.domain import User
    from tests.api.conftest import TestClient

pytestmark = [pytest.mark.asyncio]


class TestAddBookmark:
    url = "/users/bookmarks/add"

    async def test(
        self, client: TestClient, user_use_case: MagicMock, namespace: Namespace,
    ):
        # GIVEN
        user_id, file_id = namespace.owner_id, str(uuid.uuid4())
        payload = {"id": file_id}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() is None
        assert response.status_code == 200
        user_use_case.add_bookmark.assert_awaited_once_with(user_id, file_id)

    async def test_when_namespace_does_not_have_file(
        self, client: TestClient, user_use_case: MagicMock, namespace: Namespace,
    ):
        # GIVEN
        user_id, file_id = namespace.owner_id, str(uuid.uuid4())
        payload = {"id": file_id}
        user_use_case.add_bookmark.side_effect = File.NotFound
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() == FileNotFound().as_dict()
        assert response.status_code == 404
        user_use_case.add_bookmark.assert_awaited_once_with(user_id, file_id)


class TestListBookmarks:
    url = "/users/bookmarks/list"

    async def test(
        self, client: TestClient, user_use_case: MagicMock, user: User,
    ):
        # GIVEN
        bookmarks = [
            Bookmark(user_id=str(uuid.uuid4()), file_id=str(uuid.uuid4())),
            Bookmark(user_id=str(uuid.uuid4()), file_id=str(uuid.uuid4())),
        ]
        user_use_case.list_bookmarks.return_value = bookmarks
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url)
        # THEN
        assert response.json()["items"] == [str(item.file_id) for item in bookmarks]
        assert response.status_code == 200
        user_use_case.list_bookmarks.assert_awaited_once_with(user.id)

    async def test_when_no_bookmarks(
        self, client: TestClient, user_use_case: MagicMock, user: User,
    ):
        # GIVEN
        user_use_case.list_bookmarks.return_value = []
        # WHEN
        client.mock_user(user)
        response = await client.get("/users/bookmarks/list")
        # THEN
        assert response.json() == {"items": []}
        assert response.status_code == 200
        user_use_case.list_bookmarks.assert_awaited_once_with(user.id)


class TestRemoveBookmark:
    url = "/users/bookmarks/remove"

    async def test_remove_bookmark(
        self, client: TestClient, user_use_case: MagicMock, user: User,
    ):
        # GIVEN
        file_id = str(uuid.uuid4())
        payload = {"id": file_id}
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() is None
        assert response.status_code == 200
        user_use_case.remove_bookmark.assert_awaited_once_with(user.id, file_id)
