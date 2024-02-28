from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.app.users.domain import Bookmark, User

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from tests.api.conftest import TestClient

pytestmark = [pytest.mark.anyio]


class TestAddBookmarkBatch:
    url = "/users/bookmarks/add_batch"

    async def test(
        self, client: TestClient, user_use_case: MagicMock, user: User,
    ):
        # GIVEN
        file_ids = [uuid.uuid4() for _ in range(3)]
        payload = {"file_ids": [str(file_id) for file_id in file_ids]}
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() is None
        assert response.status_code == 200
        user_use_case.add_bookmark_batch.assert_awaited_once_with(
            user.id, set(file_ids)
        )


class TestListBookmarks:
    url = "/users/bookmarks/list"

    async def test(
        self, client: TestClient, user_use_case: MagicMock, user: User,
    ):
        # GIVEN
        bookmarks = [
            Bookmark(user_id=uuid.uuid4(), file_id=uuid.uuid4()),
            Bookmark(user_id=uuid.uuid4(), file_id=uuid.uuid4()),
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


class TestRemoveBookmarkBatch:
    url = "/users/bookmarks/remove_batch"

    async def test(
        self, client: TestClient, user_use_case: MagicMock, user: User,
    ):
        # GIVEN
        file_ids = [uuid.uuid4() for _ in range(3)]
        payload = {"file_ids": [str(file_id) for file_id in file_ids]}
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() is None
        assert response.status_code == 200
        user_use_case.remove_bookmark_batch.assert_awaited_once_with(
            user.id, set(file_ids)
        )
