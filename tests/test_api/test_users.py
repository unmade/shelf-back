from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app.api.users.exceptions import FileNotFound

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from fastapi import FastAPI

    from app.entities import Namespace
    from tests.conftest import TestClient

pytestmark = [pytest.mark.asyncio, pytest.mark.database(transaction=True)]


@pytest.fixture
def ns_service(app: FastAPI):
    service = app.state.provider.service
    service_mock = mock.MagicMock(service.namespace)
    with mock.patch.object(service, "namespace", service_mock) as mocked:
        yield mocked


@pytest.fixture
def user_service(app: FastAPI):
    service = app.state.provider.service
    service_mock = mock.MagicMock(service.user)
    with mock.patch.object(service, "user", service_mock) as mocked:
        yield mocked


class TestAddBookmark:
    url = "/users/bookmarks/add"

    async def test(
        self,
        client: TestClient,
        namespace: Namespace,
        ns_service: MagicMock,
        user_service: MagicMock,
    ):
        user_id = str(namespace.owner.id)
        file_id = uuid.uuid4()
        payload = {"id": str(file_id)}
        response = await client.login(user_id).post(self.url, json=payload)
        assert response.json() is None
        assert response.status_code == 200
        ns_service.has_file_with_id.assert_awaited_once_with(namespace.path, file_id)
        user_service.add_bookmark.assert_awaited_once_with(user_id, file_id)

    async def test_when_namespace_does_not_have_file(
        self,
        client: TestClient,
        namespace: Namespace,
        ns_service: MagicMock,
        user_service: MagicMock,
    ):
        ns_service.has_file_with_id.return_value = False
        user_id = str(namespace.owner.id)
        file_id = uuid.uuid4()
        payload = {"id": str(file_id)}
        response = await client.login(user_id).post(self.url, json=payload)
        assert response.json() == FileNotFound().as_dict()
        assert response.status_code == 404
        ns_service.has_file_with_id.assert_awaited_once_with(namespace.path, file_id)
        user_service.add_bookmark.assert_not_awaited()


class TestListBookmarks:
    url = "/users/bookmarks/list"

    async def test(
        self, client: TestClient, namespace: Namespace, user_service: MagicMock
    ):
        bookmarks = [uuid.uuid4(), uuid.uuid4()]
        user_service.list_bookmarks.return_value = bookmarks
        response = await client.login(namespace.owner.id).get(self.url)
        assert response.json()["items"] == [str(bookmark) for bookmark in bookmarks]
        assert response.status_code == 200

    async def test_when_no_bookmarks(
        self, client: TestClient, namespace: Namespace, user_service: MagicMock
    ):
        user_service.list_bookmarks.return_value = []
        response = await client.login(namespace.owner.id).get("/users/bookmarks/list")
        assert response.json() == {"items": []}
        assert response.status_code == 200


class TestRemoveBookmark:
    url = "/users/bookmarks/remove"

    async def test_remove_bookmark(
        self, client: TestClient, namespace: Namespace, user_service: MagicMock,
    ):
        user_id = str(namespace.owner.id)
        file_id = uuid.uuid4()
        payload = {"id": str(file_id)}
        response = await client.login(user_id).post(self.url, json=payload)
        assert response.json() is None
        assert response.status_code == 200
        user_service.remove_bookmark.assert_awaited_once_with(user_id, file_id)
