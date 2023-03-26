from __future__ import annotations

import os.path
import uuid
from typing import TYPE_CHECKING

import pytest

from app import mediatypes
from app.app.files.domain import SENTINEL_ID, File, Namespace

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.repositories import IFileRepository, INamespaceRepository
    from app.app.users.domain import User


pytestmark = [pytest.mark.asyncio]


def _make_namespace(path: str, owner_id: UUID) -> Namespace:
    return Namespace(id=SENTINEL_ID, path=path, owner_id=owner_id)


class TestGetByOwnerID:
    async def test(self, namespace_repo: INamespaceRepository, namespace: Namespace):
        retrieved_ns = await namespace_repo.get_by_owner_id(namespace.owner_id)
        assert retrieved_ns == namespace

    async def test_when_does_not_exist(self, namespace_repo: INamespaceRepository):
        owner_id = uuid.uuid4()
        with pytest.raises(Namespace.NotFound):
            await namespace_repo.get_by_owner_id(owner_id)


class TestGetByPath:
    async def test(self, namespace_repo: INamespaceRepository, namespace: Namespace):
        retrieved_ns = await namespace_repo.get_by_path(namespace.path)
        assert retrieved_ns == namespace

    async def test_when_does_not_exist(self, namespace_repo: INamespaceRepository):
        with pytest.raises(Namespace.NotFound):
            await namespace_repo.get_by_path("admin")


class TestGetSpaceUsedByOwnerID:
    @staticmethod
    def make_folder(ns_path: str, path: str, size: int) -> File:
        return File(
            id=SENTINEL_ID,
            ns_path=ns_path,
            name=os.path.basename(path),
            path=path,
            size=size,
            mediatype=mediatypes.FOLDER,
        )


    async def test_on_empty_namespace(
        self, user: User, namespace_repo: INamespaceRepository,
    ):
        namespace = await namespace_repo.save(_make_namespace("a", user.id))
        space_used = await namespace_repo.get_space_used_by_owner_id(namespace.owner_id)
        assert space_used == 0

    async def test_on_multiple_namespace(
        self,
        user: User,
        namespace_repo: INamespaceRepository,
        file_repo: IFileRepository,
    ):
        namespace_a = await namespace_repo.save(_make_namespace("a", user.id))
        await file_repo.save(self.make_folder(namespace_a.path, ".", size=10))
        space_used = await namespace_repo.get_space_used_by_owner_id(user.id)
        assert space_used == 10

        namespace_b = await namespace_repo.save(_make_namespace("b", user.id))
        await file_repo.save(self.make_folder(namespace_b.path, ".", size=5))
        space_used = await namespace_repo.get_space_used_by_owner_id(user.id)
        assert space_used == 15

    async def test_sum_only_on_home_folder(
        self,
        user: User,
        namespace_repo: INamespaceRepository,
        file_repo: IFileRepository,
    ):
        namespace_a = await namespace_repo.save(_make_namespace("a", user.id))
        await file_repo.save(self.make_folder(namespace_a.path, ".", size=10))
        await file_repo.save(self.make_folder(namespace_a.path, "folder", size=5))
        space_used = await namespace_repo.get_space_used_by_owner_id(user.id)
        assert space_used == 10


class TestSave:
    async def test(self, namespace_repo: INamespaceRepository, user: User):
        namespace = _make_namespace(user.username, user.id)
        saved_namespace = await namespace_repo.save(namespace)
        assert saved_namespace.id != SENTINEL_ID
        assert str(namespace.path) == user.username
        assert namespace.owner_id == user.id
