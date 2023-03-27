from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.api.users.exceptions import FileNotFound

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from app.app.files.domain import Namespace
    from app.app.users.domain import User
    from tests.api.conftest import TestClient

pytestmark = [pytest.mark.asyncio]


class TestAddBookmark:
    url = "/users/bookmarks/add"

    async def test(
        self,
        client: TestClient,
        namespace: Namespace,
        ns_use_case: MagicMock,
        user_service: MagicMock,
    ):
        # GIVEN
        ns_path = namespace.path
        user_id = namespace.owner_id
        file_id = uuid.uuid4()
        payload = {"id": str(file_id)}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() is None
        assert response.status_code == 200
        ns_use_case.has_item_with_id.assert_awaited_once_with(ns_path, str(file_id))
        user_service.add_bookmark.assert_awaited_once_with(user_id, file_id)

    async def test_when_namespace_does_not_have_file(
        self,
        client: TestClient,
        namespace: Namespace,
        ns_use_case: MagicMock,
        user_service: MagicMock,
    ):
        # GIVEN
        ns_path = namespace.path
        file_id = uuid.uuid4()
        payload = {"id": str(file_id)}
        ns_use_case.has_item_with_id.return_value = False
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() == FileNotFound().as_dict()
        assert response.status_code == 404
        ns_use_case.has_item_with_id.assert_awaited_once_with(ns_path, str(file_id))
        user_service.add_bookmark.assert_not_awaited()


class TestListBookmarks:
    url = "/users/bookmarks/list"

    async def test(
        self, client: TestClient, user: User, user_service: MagicMock
    ):
        # GIVEN
        bookmarks = [uuid.uuid4(), uuid.uuid4()]
        user_service.list_bookmarks.return_value = bookmarks
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url)
        # THEN
        assert response.json()["items"] == [str(bookmark) for bookmark in bookmarks]
        assert response.status_code == 200

    async def test_when_no_bookmarks(
        self, client: TestClient, user: User, user_service: MagicMock
    ):
        # GIVEN
        user_service.list_bookmarks.return_value = []
        # WHEN
        client.mock_user(user)
        response = await client.get("/users/bookmarks/list")
        # THEN
        assert response.json() == {"items": []}
        assert response.status_code == 200


class TestRemoveBookmark:
    url = "/users/bookmarks/remove"

    async def test_remove_bookmark(
        self, client: TestClient, user: User, user_service: MagicMock,
    ):
        # GIVEN
        file_id = uuid.uuid4()
        payload = {"id": str(file_id)}
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() is None
        assert response.status_code == 200
        user_service.remove_bookmark.assert_awaited_once_with(user.id, file_id)
