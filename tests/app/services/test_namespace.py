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
    from app.domain.entities import File, User

    from .conftest import FileFactory, FolderFactory

pytestmark = [pytest.mark.asyncio, pytest.mark.database]


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

    @pytest.mark.database(transaction=True)
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


class TestHasFileWithID:
    async def test(
        self, namespace: Namespace, file: File, namespace_service: NamespaceService
    ):
        exists = await namespace_service.has_file_with_id(namespace.path, file.id)
        assert exists is True


class TestMoveFile:
    async def test_moving_a_file(
        self,
        namespace: Namespace,
        file_factory: FileFactory,
        namespace_service: NamespaceService,
    ):
        ns_path = namespace.path
        file = await file_factory(namespace.path, "f.txt")
        moved_file = await namespace_service.move_file(ns_path, file.path, ".f.txt")
        assert moved_file.name == ".f.txt"
        assert moved_file.path == ".f.txt"
        assert await namespace_service.storage.exists(namespace.path, ".f.txt")
        assert await namespace_service.db.file.exists_at_path(namespace.path, ".f.txt")

    async def test_moving_a_folder(
        self,
        namespace_service: NamespaceService,
        namespace: Namespace,
        file_factory: FileFactory,
    ):
        ns_path = namespace.path
        await file_factory(ns_path, path="a/b/f.txt")
        # rename folder 'b' to 'c'
        moved_file = await namespace_service.move_file(ns_path, "a/b", "a/c")
        assert moved_file.name == "c"
        assert moved_file.path == "a/c"

        assert not await namespace_service.storage.exists(ns_path, "a/b")
        assert not await namespace_service.db.file.exists_at_path(ns_path, "a/b")
        assert not await namespace_service.storage.exists(ns_path, "a/b/f.txt")
        assert not await namespace_service.db.file.exists_at_path(ns_path, "a/b/f.txt")

        assert await namespace_service.storage.exists(ns_path, "a/c")
        assert await namespace_service.db.file.exists_at_path(ns_path, "a/c")
        assert await namespace_service.storage.exists(ns_path, "a/c/f.txt")
        assert await namespace_service.db.file.exists_at_path(ns_path, "a/c/f.txt")

    async def test_updating_parents_size(
        self,
        namespace: Namespace,
        file_factory: FileFactory,
        namespace_service: NamespaceService,
    ):
        ns_path = namespace.path
        await file_factory(ns_path, "a/b/f.txt")
        await file_factory(ns_path, "a/b/c/x.txt")
        await file_factory(ns_path, "a/b/c/y.txt")
        await file_factory(ns_path, "a/g/z.txt")

        await namespace_service.move_file(ns_path, "a/b/c", "a/g/c")

        paths = [".", "a", "a/b", "a/g"]
        h, a, b, g = await namespace_service.db.file.get_by_path_batch(ns_path, paths)
        assert h.size == 40
        assert a.size == 40
        assert b.size == 10
        assert g.size == 30

    async def test_case_sensitive_renaming(
        self,
        namespace: Namespace,
        file_factory: FileFactory,
        namespace_service: NamespaceService,
    ):
        ns_path = namespace.path
        await file_factory(namespace.path, path="file.txt")
        moved_file = await namespace_service.move_file(ns_path, "file.txt", "File.txt")
        assert moved_file.name == "File.txt"
        assert moved_file.path == "File.txt"
        assert await namespace_service.storage.exists(ns_path, "File.txt")
        assert await namespace_service.db.file.exists_at_path(ns_path, "File.txt")

    async def test_case_insensitiveness(
        self,
        namespace: Namespace,
        file_factory: FileFactory,
        folder_factory: FolderFactory,
        namespace_service: NamespaceService,
    ):
        ns_path = namespace.path
        await folder_factory(namespace.path, "a")
        await folder_factory(namespace.path, "a/B")
        await file_factory(namespace.path, "a/f")

        # move file from 'a/f' to 'a/B/F.TXT'
        moved_file = await namespace_service.move_file(ns_path, "A/F", "A/b/F.TXT")
        assert moved_file.name == "F.TXT"
        assert moved_file.path == "a/B/F.TXT"

        f = await namespace_service.db.file.get_by_path(ns_path, "a/b/f.txt")
        assert f.name == "F.TXT"
        assert f.path == "a/B/F.TXT"

    async def test_when_path_does_not_exist(
        self, namespace: Namespace, namespace_service: NamespaceService
    ):
        with pytest.raises(errors.FileNotFound):
            await namespace_service.move_file(namespace.path, "f.txt", "a/f.txt")

    async def test_when_next_path_is_taken(
        self,
        namespace: Namespace,
        file_factory: FileFactory,
        namespace_service: NamespaceService,
    ):
        await file_factory(namespace.path, "a/b/x.txt")
        await file_factory(namespace.path, "a/c/y.txt")
        with pytest.raises(errors.FileAlreadyExists):
            await namespace_service.move_file(namespace.path, "a/b", "a/c")

    async def test_when_next_path_parent_is_missing(
        self,
        namespace: Namespace,
        file_factory: FileFactory,
        namespace_service: NamespaceService,
    ):
        await file_factory(namespace.path, "f.txt")
        with pytest.raises(errors.MissingParent):
            await namespace_service.move_file(namespace.path, "f.txt", "a/f.txt")

    async def test_when_next_path_is_not_a_folder(
        self,
        namespace: Namespace,
        file_factory: FileFactory,
        namespace_service: NamespaceService,
    ):
        await file_factory(namespace.path, "x.txt")
        await file_factory(namespace.path, "y")
        with pytest.raises(errors.NotADirectory):
            await namespace_service.move_file(namespace.path, "x.txt", "y/x.txt")

    @pytest.mark.parametrize("path", [".", "Trash", "trash"])
    async def test_when_moving_to_a_special_folder(
        self, namespace: Namespace, namespace_service: NamespaceService, path: str
    ):
        with pytest.raises(AssertionError) as excinfo:
            await namespace_service.move_file(namespace.path, path, "a/b")
        assert str(excinfo.value) == "Can't move Home or Trash folder."

    @pytest.mark.parametrize(["a", "b"], [
        ("a/b", "a/b/b"),
        ("a/B", "A/b/B"),
    ])
    async def test_when_moving_to_itself(
        self,
        namespace: Namespace,
        namespace_service: NamespaceService,
        a: str,
        b: str,
    ):
        with pytest.raises(AssertionError) as excinfo:
            await namespace_service.move_file(namespace.path, a, b)
        assert str(excinfo.value) == "Can't move to itself."
