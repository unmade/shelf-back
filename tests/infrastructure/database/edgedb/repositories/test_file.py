from __future__ import annotations

import operator
import uuid
from typing import TYPE_CHECKING

import pytest

from app import errors
from app.app.repositories.file import FileUpdate
from app.domain.entities import SENTINEL_ID, File
from app.infrastructure.database.edgedb.db import db_context

if TYPE_CHECKING:
    from app.domain.entities import Namespace
    from app.infrastructure.database.edgedb.repositories import FileRepository
    from app.typedefs import StrOrUUID
    from tests.infrastructure.database.edgedb.conftest import FileFactory, FolderFactory

pytestmark = [pytest.mark.asyncio]


async def _get_by_id(file_id: StrOrUUID) -> File:
    query = """
        SELECT
            File {
                id, name, path, size, mtime, mediatype: { name }, namespace: { path }
            }
        FILTER
            .id = <uuid>$file_id
    """
    obj = await db_context.get().query_required_single(query, file_id=file_id)
    return File.construct(
        id=obj.id,
        name=obj.name,
        ns_path=obj.namespace.path,
        path=obj.path,
        size=obj.size,
        mtime=obj.mtime,
        mediatype=obj.mediatype.name,
    )


class TestExistsAtPath:
    async def test_when_exists(self, file_repo: FileRepository, file: File):
        exists = await file_repo.exists_at_path(file.ns_path, file.path)
        assert exists is True

    async def test_when_does_not_exist(
        self, namespace: Namespace, file_repo: FileRepository
    ):
        path = "f.txt"
        exists = await file_repo.exists_at_path(namespace.path, path)
        assert exists is False


class TestExistsWithID:
    async def test_when_exists(self, file_repo: FileRepository, file: File):
        exists = await file_repo.exists_with_id(file.ns_path, file.id)
        assert exists is True

    async def test_when_does_not_exist(
        self, file_repo: FileRepository, namespace: Namespace,
    ):
        file_id = uuid.uuid4()
        exists = await file_repo.exists_with_id(namespace.path, file_id)
        assert exists is False


class TestGetByPath:
    async def test(self, file_repo: FileRepository, file: File):
        file_in_db = await file_repo.get_by_path(file.ns_path, file.path)
        assert file_in_db == file

    async def test_when_file_does_not_exist(
        self, namespace: Namespace, file_repo: FileRepository
    ):
        path = "f.txt"
        with pytest.raises(errors.FileNotFound):
            await file_repo.get_by_path(namespace.path, path)


class TestGetByPathBatch:
    async def test(
        self, file_repo: FileRepository, file_factory: FileFactory, namespace: Namespace
    ):
        files = [await file_factory(namespace.path) for _ in range(3)]
        paths = [file.path for file in files]
        result = await file_repo.get_by_path_batch(namespace.path, paths)
        assert result == sorted(files, key=operator.attrgetter("path"))

    async def test_when_some_file_does_not_exist(
        self, file_repo: FileRepository, file: File,
    ):
        paths = [file.path, f"{uuid.uuid4()}.txt"]
        result = await file_repo.get_by_path_batch(file.ns_path, paths)
        assert result == [file]


class TestIncrSizeBatch:
    async def test(
        self,
        file_repo: FileRepository,
        folder_factory: FolderFactory,
        namespace: Namespace,
    ):
        await folder_factory(namespace.path, "a")
        await folder_factory(namespace.path, "a/b")
        await folder_factory(namespace.path, "a/c")

        await file_repo.incr_size_batch(namespace.path, paths=["a", "a/c"], value=16)

        paths = ["a", "a/b", "a/c"]
        a, b, c = await file_repo.get_by_path_batch(namespace.path, paths=paths)
        assert a.size == 16
        assert b.size == 0
        assert c.size == 16

    async def test_case_insensitiveness(
        self,
        file_repo: FileRepository,
        folder_factory: FolderFactory,
        namespace: Namespace,
    ):
        await folder_factory(namespace.path, "a")
        await folder_factory(namespace.path, "a/b")
        await folder_factory(namespace.path, "a/C")

        await file_repo.incr_size_batch(namespace.path, paths=["A", "A/c"], value=16)

        paths = ["a", "a/b", "a/c"]
        a, b, c = await file_repo.get_by_path_batch(namespace.path, paths=paths)
        assert a.size == 16
        assert b.size == 0
        assert c.size == 16

    async def test_when_incrementing_zero_size(self, file_repo: FileRepository):
        # here we tesh early return in the function. The path 'a/b' does not exist and
        # if we were to hit the database we would fail with an error
        await file_repo.incr_size_batch("namespace", paths=["a/b"], value=0)


class TestReplacePathPrefix:
    async def test(
        self, file_repo: FileRepository, file_factory: FileFactory, namespace: Namespace
    ):
        ns_path = namespace.path
        await file_factory(ns_path, "a/b/c/f.txt")
        await file_factory(ns_path, "a/b/c/d/f.txt")
        await file_repo.replace_path_prefix(ns_path, "a/b/c", "d")
        results = await file_repo.get_by_path_batch(ns_path, ["d/f.txt", "d/d/f.txt"])
        assert len(results) == 2
        assert results[0].path == "d/d/f.txt"
        assert results[1].path == "d/f.txt"

    async def test_case_insensitiveness(
        self, file_repo: FileRepository, file_factory: FileFactory, namespace: Namespace
    ):
        ns_path = namespace.path
        await file_factory(ns_path, "A/b/C/f.txt")
        await file_factory(ns_path, "a/B/c/d/f.txt")
        await file_repo.replace_path_prefix(ns_path, "a/b/C", "d")
        results = await file_repo.get_by_path_batch(ns_path, ["d/f.txt", "d/d/f.txt"])
        assert len(results) == 2

    async def test_replacing_only_the_first_occurence(
        self, file_repo: FileRepository, file_factory: FileFactory, namespace: Namespace
    ):
        ns_path = namespace.path
        await file_factory(ns_path, "a/b/a/b/f.txt")
        await file_repo.replace_path_prefix(ns_path, "a/b", "c")
        file = await file_repo.get_by_path(ns_path, "c/a/b/f.txt")
        assert file.path == "c/a/b/f.txt"


class TestSave:
    async def test(self, file_repo: FileRepository, namespace: Namespace):
        saved_file = await file_repo.save(
            File(
                id=SENTINEL_ID,
                name="f.txt",
                ns_path=namespace.path,
                path="folder/f.txt",
                size=10,
                mtime=12.34,
                mediatype="plain/text",
            )
        )
        assert saved_file.id != SENTINEL_ID

        file = await _get_by_id(saved_file.id)
        assert file == saved_file

    async def test_when_file_at_path_already_exists(
        self, file_repo: FileRepository, file: File
    ):
        file_to_save = File(
            id=SENTINEL_ID,
            name=file.name,
            ns_path=file.ns_path,
            path=file.path,
            size=10,
            mtime=12.34,
            mediatype="plain/text",
        )
        with pytest.raises(errors.FileAlreadyExists):
            await file_repo.save(file_to_save)


class TestUpdate:
    async def test(self, file_repo: FileRepository, file: File):
        file_update = FileUpdate(
            id=file.id,
            name=f".{file.name}",
            path=f".{file.path}",
        )
        updated_file = await file_repo.update(file_update)
        assert updated_file.name == f".{file.name}"
        assert updated_file.path == f".{file.path}"
        file_in_db = await _get_by_id(file.id)
        assert file_in_db == updated_file