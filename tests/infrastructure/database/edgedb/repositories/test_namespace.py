from __future__ import annotations

import os.path
from typing import TYPE_CHECKING

import pytest

from app import mediatypes
from app.domain.entities import SENTINEL_ID, File, Namespace

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.repositories import IFileRepository, INamespaceRepository
    from app.domain.entities import User


pytestmark = [pytest.mark.asyncio]


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

    @staticmethod
    def make_namespace(path: str, owner_id: UUID) -> Namespace:
        return Namespace(id=SENTINEL_ID, path=path, owner_id=owner_id)

    async def test_on_empty_namespace(
        self, user: User, namespace_repo: INamespaceRepository,
    ):
        namespace = await namespace_repo.save(self.make_namespace("a", user.id))
        space_used = await namespace_repo.get_space_used_by_owner_id(namespace.owner_id)
        assert space_used == 0

    async def test_on_multiple_namespace(
        self,
        user: User,
        namespace_repo: INamespaceRepository,
        file_repo: IFileRepository,
    ):
        namespace_a = await namespace_repo.save(self.make_namespace("a", user.id))
        await file_repo.save(self.make_folder(namespace_a.path, ".", size=10))
        space_used = await namespace_repo.get_space_used_by_owner_id(user.id)
        assert space_used == 10

        namespace_b = await namespace_repo.save(self.make_namespace("b", user.id))
        await file_repo.save(self.make_folder(namespace_b.path, ".", size=5))
        space_used = await namespace_repo.get_space_used_by_owner_id(user.id)
        assert space_used == 15

    async def test_sum_only_on_home_folder(
        self,
        user: User,
        namespace_repo: INamespaceRepository,
        file_repo: IFileRepository,
    ):
        namespace_a = await namespace_repo.save(self.make_namespace("a", user.id))
        await file_repo.save(self.make_folder(namespace_a.path, ".", size=10))
        await file_repo.save(self.make_folder(namespace_a.path, "folder", size=5))
        space_used = await namespace_repo.get_space_used_by_owner_id(user.id)
        assert space_used == 10
