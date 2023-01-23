from __future__ import annotations

from io import BytesIO
from pathlib import PurePath
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app import errors, taskgroups
from app.domain.entities import SENTINEL_ID, Folder, Namespace

if TYPE_CHECKING:
    from app.app.services import NamespaceService
    from app.domain.entities import User

pytestmark = [pytest.mark.asyncio]


class TestAddFile:
    async def test(self, namespace: Namespace, namespace_service: NamespaceService):
        content = BytesIO(b"Dummy file")
        file = await namespace_service.add_file(namespace.path, "f.txt", content)
        assert file.name == "f.txt"
        assert file.path == "f.txt"
        assert file.size == 10
        assert file.mediatype == 'text/plain'

    async def test_saving_an_image(
        self,
        namespace: Namespace,
        namespace_service: NamespaceService,
        image_content: BytesIO,
    ):
        content = image_content
        file = await namespace_service.add_file(namespace.path, "im.jpeg", content)
        assert file.mediatype == "image/jpeg"

    async def test_creating_missing_parents(
        self, namespace: Namespace, namespace_service: NamespaceService
    ):
        content = BytesIO(b"Dummy file")
        file = await namespace_service.add_file(namespace.path, "a/b/f.txt", content)
        assert file.name == "f.txt"
        assert file.path == "a/b/f.txt"

        paths = ["a", "a/b"]
        db = namespace_service.db
        a, b = await db.file.get_by_path_batch(namespace.path,  paths=paths)
        assert a.path == "a"
        assert b.path == "a/b"

    async def test_parents_size_is_updated(
        self, namespace: Namespace, namespace_service: NamespaceService
    ):
        content = BytesIO(b"Dummy file")
        await namespace_service.add_file(namespace.path, "a/b/f.txt", content)
        paths = [".", "a", "a/b"]
        db = namespace_service.db
        home, a, b = await db.file.get_by_path_batch(namespace.path, paths=paths)
        assert home.size == 10
        assert a.size == 10
        assert b.size == 10

    @pytest.mark.skip
    async def test_saving_files_concurrently(
        self, namespace: Namespace, namespace_service: NamespaceService
    ):
        CONCURRENCY = 50
        parent = PurePath("a/b/c")
        paths = [parent / str(name) for name in range(CONCURRENCY)]
        contents = [BytesIO(b"1") for _ in range(CONCURRENCY)]

        await namespace_service.create_folder(namespace.path, parent)

        await taskgroups.gather(*(
            namespace_service.add_file(namespace.path, path, content)
            for path, content in zip(paths, contents, strict=True)
        ))

        db = namespace_service.db
        count = len(await db.file.get_by_path_batch(namespace.path, paths))
        assert count == CONCURRENCY

        home = await db.file.get_by_path(namespace.path, ".")
        assert home.size == CONCURRENCY

    async def test_when_file_path_already_taken(
        self, namespace: Namespace, namespace_service: NamespaceService
    ):
        content = BytesIO(b"Dummy file")
        await namespace_service.add_file(namespace.path, "f.txt", content)
        await namespace_service.add_file(namespace.path, "f.txt", content)

        db = namespace_service.db
        paths = ["f.txt", "f (1).txt"]
        f_1, f = await db.file.get_by_path_batch(namespace.path, paths)
        assert f.path == "f.txt"
        assert f_1.path == "f (1).txt"

    async def test_when_parent_path_is_file(
        self, namespace: Namespace, namespace_service: NamespaceService
    ):
        content = BytesIO(b"Dummy file")
        await namespace_service.add_file(namespace.path, "f.txt", content)
        with pytest.raises(errors.NotADirectory):
            await namespace_service.add_file(namespace.path, "f.txt/f.txt", content)


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
        await namespace_service.db.folder.save(
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
