from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.app.files.domain import Namespace
from app.app.infrastructure.database import SENTINEL_ID

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.files.repositories import INamespaceRepository
    from app.app.users.domain import User

    from ..conftest import FolderFactory


pytestmark = [pytest.mark.anyio, pytest.mark.database]


def _make_namespace(path: str, owner_id: UUID) -> Namespace:
    return Namespace(id=SENTINEL_ID, path=path, owner_id=owner_id)


class TestGetByOwnerID:
    async def test(
        self, namespace_repo: INamespaceRepository, namespace: Namespace
    ):
        retrieved_ns = await namespace_repo.get_by_owner_id(namespace.owner_id)
        assert retrieved_ns == namespace

    async def test_when_does_not_exist(self, namespace_repo: INamespaceRepository):
        with pytest.raises(Namespace.NotFound):
            await namespace_repo.get_by_owner_id(uuid.uuid4())


class TestGetByPath:
    async def test(
        self, namespace_repo: INamespaceRepository, namespace: Namespace
    ):
        retrieved_ns = await namespace_repo.get_by_path(namespace.path)
        assert retrieved_ns == namespace

    async def test_when_does_not_exist(self, namespace_repo: INamespaceRepository):
        with pytest.raises(Namespace.NotFound):
            await namespace_repo.get_by_path("nonexistent")


class TestGetSpaceUsedByOwnerID:
    async def test_on_empty_namespace(
        self, user: User, namespace_repo: INamespaceRepository
    ):
        namespace = await namespace_repo.save(_make_namespace("a", user.id))
        space_used = await namespace_repo.get_space_used_by_owner_id(namespace.owner_id)
        assert space_used == 0

    async def test_on_multiple_namespaces(
        self,
        user: User,
        namespace_repo: INamespaceRepository,
        folder_factory: FolderFactory,
    ):
        namespace_a = await namespace_repo.save(_make_namespace("a", user.id))
        await folder_factory(namespace_a.path, path=".", size=10)
        space_used = await namespace_repo.get_space_used_by_owner_id(user.id)
        assert space_used == 10

        namespace_b = await namespace_repo.save(_make_namespace("b", user.id))
        await folder_factory(namespace_b.path, path=".", size=10)
        space_used = await namespace_repo.get_space_used_by_owner_id(user.id)
        assert space_used == 20


class TestSave:
    async def test(self, namespace_repo: INamespaceRepository, user: User):
        namespace = _make_namespace(user.username, user.id)
        saved = await namespace_repo.save(namespace)
        assert saved.id != SENTINEL_ID
        assert saved.path == user.username
        assert saved.owner_id == user.id
