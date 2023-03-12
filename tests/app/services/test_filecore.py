from __future__ import annotations

import operator
import os.path
import uuid
from io import BytesIO
from pathlib import PurePath
from typing import IO, TYPE_CHECKING

import pytest

from app import errors, mediatypes, taskgroups
from app.domain.entities import File

if TYPE_CHECKING:
    from app.app.services import FileCoreService
    from app.domain.entities import Namespace

    from .conftest import FileFactory, FolderFactory

pytestmark = [pytest.mark.asyncio, pytest.mark.database]


def _make_file(
    ns_path: str, path: str, size: int = 10, mediatype: str = "plain/text"
) -> File:
    return File(
        id=uuid.uuid4(),
        ns_path=ns_path,
        name=os.path.basename(path),
        path=path,
        size=size,
        mediatype=mediatype,
    )


class TestCreateFile:
    async def test(self, filecore: FileCoreService, namespace: Namespace):
        content = BytesIO(b"Dummy file")
        file = await filecore.create_file(namespace.path, "f.txt", content)
        assert file.name == "f.txt"
        assert file.path == "f.txt"
        assert file.size == 10
        assert file.mediatype == 'text/plain'

    async def test_saving_an_image(
        self,
        filecore: FileCoreService,
        namespace: Namespace,
        image_content: BytesIO,
    ):
        content = image_content
        file = await filecore.create_file(namespace.path, "im.jpeg", content)
        assert file.mediatype == "image/jpeg"

    async def test_creating_missing_parents(
        self, filecore: FileCoreService, namespace: Namespace,
    ):
        content = BytesIO(b"Dummy file")
        file = await filecore.create_file(namespace.path, "a/b/f.txt", content)
        assert file.name == "f.txt"
        assert file.path == "a/b/f.txt"

        paths = ["a", "a/b"]
        db = filecore.db
        a, b = await db.file.get_by_path_batch(namespace.path,  paths=paths)
        assert a.path == "a"
        assert b.path == "a/b"

    async def test_parents_size_is_updated(
        self, filecore: FileCoreService, namespace: Namespace
    ):
        content = BytesIO(b"Dummy file")
        await filecore.create_file(namespace.path, "a/b/f.txt", content)
        paths = [".", "a", "a/b"]
        db = filecore.db
        home, a, b = await db.file.get_by_path_batch(namespace.path, paths=paths)
        assert home.size == 10
        assert a.size == 10
        assert b.size == 10

    @pytest.mark.database(transaction=True)
    async def test_saving_files_concurrently(
        self, filecore: FileCoreService, namespace: Namespace,
    ):
        CONCURRENCY = 50
        parent = PurePath("a/b/c")
        paths = [parent / str(name) for name in range(CONCURRENCY)]
        contents = [BytesIO(b"1") for _ in range(CONCURRENCY)]

        await filecore.create_folder(namespace.path, parent)

        await taskgroups.gather(*(
            filecore.create_file(namespace.path, path, content)
            for path, content in zip(paths, contents, strict=True)
        ))

        db = filecore.db
        count = len(await db.file.get_by_path_batch(namespace.path, paths))
        assert count == CONCURRENCY

        home = await db.file.get_by_path(namespace.path, ".")
        assert home.size == CONCURRENCY

    async def test_when_file_path_already_taken(
        self, filecore: FileCoreService, namespace: Namespace,
    ):
        content = BytesIO(b"Dummy file")
        await filecore.create_file(namespace.path, "f.txt", content)
        await filecore.create_file(namespace.path, "f.txt", content)

        db = filecore.db
        paths = ["f.txt", "f (1).txt"]
        f_1, f = await db.file.get_by_path_batch(namespace.path, paths)
        assert f.path == "f.txt"
        assert f_1.path == "f (1).txt"

    async def test_when_parent_path_is_file(
        self, filecore: FileCoreService, namespace: Namespace,
    ):
        content = BytesIO(b"Dummy file")
        await filecore.create_file(namespace.path, "f.txt", content)
        with pytest.raises(errors.NotADirectory):
            await filecore.create_file(namespace.path, "f.txt/f.txt", content)


class TestDownload:
    def test(self, filecore: FileCoreService, file: File):
        content = filecore.download(file.ns_path, file.path)
        assert content.read() == b"Dummy file"


class TestIterByMediatypes:
    async def test_iter_by_mediatypes(
        self,
        filecore: FileCoreService,
        file_factory: FileFactory,
        namespace: Namespace,
        image_content: IO[bytes],
    ):
        ns_path = str(namespace.path)
        await file_factory(ns_path, "plain.txt")
        jpg_1 = await file_factory(ns_path, "img (1).jpg", content=image_content)
        jpg_2 = await file_factory(ns_path, "img (2).jpg", content=image_content)

        mediatypes = ["image/jpeg"]
        batches = filecore.iter_by_mediatypes(ns_path, mediatypes, batch_size=1)
        result = [files async for files in batches]
        assert len(result) == 2
        actual = [*result[0], *result[1]]
        assert sorted(actual, key=operator.attrgetter("mtime")) == [jpg_1, jpg_2]

    async def test_iter_by_mediatypes_when_no_files(
        self, filecore: FileCoreService, namespace: Namespace
    ):
        ns_path = namespace.path
        mediatypes = ["image/jpeg", "image/png"]
        batches = filecore.iter_by_mediatypes(ns_path, mediatypes, batch_size=1)
        result = [files async for files in batches]
        assert result == []


class TestReindex:
    async def test_creating_missing_files(
        self,
        filecore: FileCoreService,
        namespace: Namespace,
        image_content: IO[bytes],
    ):
        # GIVEN
        db = filecore.db
        storage = filecore.storage
        dummy_text = b"Dummy file"

        # these files exist in the storage, but not in the database
        await storage.makedirs(namespace.path, "a")
        await storage.makedirs(namespace.path, "b")
        await storage.save(namespace.path, "b/f.txt", content=BytesIO(dummy_text))
        await storage.save(namespace.path, "im.jpeg", content=image_content)

        # WHEN
        await filecore.reindex(namespace.path, ".")

        # THEN
        # ensure home size is correct
        home = await db.file.get_by_path(namespace.path, ".")
        assert home.size == 1661

        # ensure missing files in the database has been created
        paths = ["a", "b", "b/f.txt", "im.jpeg"]
        a, b, f, i = await db.file.get_by_path_batch(namespace.path, paths=paths)
        assert a.is_folder()
        assert a.size == 0
        assert b.is_folder()
        assert b.size == 10
        assert f.size == len(dummy_text)
        assert f.mediatype == "text/plain"
        assert i.mediatype == "image/jpeg"
        assert i.size == image_content.seek(0, 2)

    async def test_removing_dangling_files(
        self,
        filecore: FileCoreService,
        namespace: Namespace,
    ):
        # GIVEN
        db = filecore.db

        # these files exist in the database, but not in the storage
        await db.file.save_batch([
            _make_file(namespace.path, "c", size=0, mediatype=mediatypes.FOLDER),
            _make_file(namespace.path, "c/d", size=0, mediatype=mediatypes.FOLDER),
            _make_file(namespace.path, "c/d/f.txt", size=32),
        ])

        # WHEN
        await filecore.reindex(namespace.path, ".")

        # THEN
        # ensure home size is updated
        home = await db.file.get_by_path(namespace.path, ".")
        assert home.size == 0

        # ensure stale files has been deleted
        assert not await db.file.exists_at_path(namespace.path, "c")
        assert not await db.file.exists_at_path(namespace.path, "c/d")
        assert not await db.file.exists_at_path(namespace.path, "c/d/f.txt")

    async def test_when_files_consistent(
        self,
        filecore: FileCoreService,
        namespace: Namespace,
        file_factory: FileFactory,
    ):
        # GIVEN
        db = filecore.db
        file = await file_factory(namespace.path, path="e/g/f.txt")

        # WHEN
        await filecore.reindex(namespace.path, ".")

        # THEN
        # parent size is correct
        e = await db.file.get_by_path(namespace.path, "e")
        assert e.size == file.size

        # ensure correct files remain the same
        assert await db.file.exists_at_path(namespace.path, "e/g/f.txt")

    async def test_when_path_is_missing_in_the_db(
        self,
        filecore: FileCoreService,
        namespace: Namespace,
    ):
        await filecore.storage.makedirs(namespace.path, "a")
        await filecore.reindex(namespace.path, "a")
        assert await filecore.db.file.exists_at_path(namespace.path, "a")

    async def test_when_path_is_present_in_the_db(
        self,
        filecore: FileCoreService,
        namespace: Namespace,
        folder_factory: FolderFactory,
    ):
        db = filecore.db
        await folder_factory(namespace.path, path="a")
        await filecore.reindex(namespace.path, "a")
        assert await db.file.exists_at_path(namespace.path, "a")

    async def test_when_path_is_a_file(
        self,
        filecore: FileCoreService,
        namespace: Namespace,
        file_factory: FileFactory,
    ):
        await file_factory(namespace.path, path="a")
        with pytest.raises(errors.NotADirectory):
            await filecore.reindex(namespace.path, "a")

    async def test_when_path_is_a_file_in_the_storage(
        self,
        filecore: FileCoreService,
        namespace: Namespace,
    ):
        await filecore.storage.save(namespace.path, "a", content=BytesIO(b"Dummy"))
        with pytest.raises(errors.NotADirectory):
            await filecore.reindex(namespace.path, "a")
        assert not await filecore.db.file.exists_at_path(namespace.path, "a")
