from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app import errors
from app.domain.entities import SENTINEL_ID, Folder, Namespace

if TYPE_CHECKING:
    from app.app.services import NamespaceService
    from app.domain.entities import User

pytestmark = [pytest.mark.asyncio]


class TestCreate:
    async def test(self, user: User, namespace_service: NamespaceService):
        namespace = await namespace_service.create("admin", owner_id=user.id)
        assert namespace.id is not None
        assert namespace == Namespace.construct(
            id=mock.ANY,
            path="admin",
            owner_id=user.id,
        )


class TestCreateFolder:
    async def test(self, namespace: Namespace, namespace_service: NamespaceService):
        folder = await namespace_service.create_folder(namespace.path, "New Folder")
        assert folder.name == "New Folder"

    async def test_nested_path(
        self, namespace: Namespace, namespace_service: NamespaceService
    ):
        folder = await namespace_service.create_folder(namespace.path, "a/b/c/f")
        assert folder.path == "a/b/c/f"

    async def test_path_is_case_insensitive(
        self, namespace: Namespace, namespace_service: NamespaceService
    ):
        b = await namespace_service.create_folder(namespace.path, "A/b")
        c = await namespace_service.create_folder(namespace.path, "a/B/c")

        assert b.path == "A/b"
        assert c.path == "A/b/c"

    async def test_when_folder_exists(
        self, namespace: Namespace, namespace_service: NamespaceService
    ):
        folder = await namespace_service.create_folder(namespace.path, "New Folder")
        with pytest.raises(errors.FileAlreadyExists):
            folder = await namespace_service.create_folder(namespace.path, folder.path)

    async def test_when_path_is_not_a_directory(
        self, namespace: Namespace, namespace_service: NamespaceService
    ):
        await namespace_service.folder_repo.save(
            Folder(
                id=SENTINEL_ID,
                ns_path=namespace.path,
                name="f.txt",
                path="f.txt",
                mediatype='plain/text',
            )
        )

        with pytest.raises(errors.NotADirectory):
            await namespace_service.create_folder(namespace.path, "f.txt/folder")
