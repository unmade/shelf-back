from __future__ import annotations

import operator
import uuid
from typing import TYPE_CHECKING, cast

import pytest

from app.app.files.domain import File
from app.app.files.repositories.file import FileUpdate
from app.app.infrastructure.database import SENTINEL_ID
from app.infrastructure.database.edgedb.db import db_context

if TYPE_CHECKING:
    from app.app.files.domain import AnyPath, Namespace
    from app.infrastructure.database.edgedb.repositories import FileRepository
    from app.typedefs import StrOrUUID
    from tests.infrastructure.database.edgedb.conftest import (
        FileFactory,
        FolderFactory,
        MountFactory,
        NamespaceFactory,
        UserFactory,
    )

pytestmark = [pytest.mark.asyncio, pytest.mark.database]


async def _exists_with_id(file_id: StrOrUUID) -> bool:
    query = """SELECT EXISTS(SELECT File FILTER .id = <uuid>$file_id)"""
    return cast(
        bool,
        await db_context.get().query_required_single(query, file_id=file_id)
    )


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
    return File(
        id=obj.id,
        name=obj.name,
        ns_path=obj.namespace.path,
        path=obj.path,
        size=obj.size,
        mtime=obj.mtime,
        mediatype=obj.mediatype.name,
    )


async def _get_by_path(ns_path: AnyPath, path: AnyPath) -> File:
    query = """
        SELECT
            File {
                id, name, path, size, mtime, mediatype: { name }, namespace: { path }
            }
        FILTER
            .path = <str>$path
            AND
            .namespace.path = <str>$ns_path
        LIMIT 1
    """
    conn = db_context.get()
    obj = await conn.query_required_single(query, ns_path=str(ns_path), path=str(path))
    return File(
        id=obj.id,
        name=obj.name,
        ns_path=obj.namespace.path,
        path=obj.path,
        size=obj.size,
        mtime=obj.mtime,
        mediatype=obj.mediatype.name,
    )


class TestCountByPattern:
    async def test(
        self,
        file_repo: FileRepository,
        file_factory: FileFactory,
        namespace: Namespace,
    ):
        ns_path = namespace.path
        await file_factory(ns_path, "f (f).txt")
        await file_factory(ns_path, "f (1).txt")
        await file_factory(ns_path, "f (2).txt")
        count = await file_repo.count_by_path_pattern(ns_path, "f \\(\\d+\\).txt")
        assert count == 2

    async def test_when_no_match_exists(
        self, file_repo: FileRepository, namespace: Namespace
    ):
        ns_path = namespace.path
        count = await file_repo.count_by_path_pattern(ns_path, "f \\(\\d+\\).txt")
        assert count == 0


class TestDelete:
    async def test(self, file_repo: FileRepository, file: File):
        deleted_file = await file_repo.delete(file.ns_path, file.path)
        assert deleted_file == file
        assert not await _exists_with_id(file.id)

    async def test_when_does_not_exist(self, file_repo: FileRepository):
        with pytest.raises(File.NotFound):
            await file_repo.delete("admin", "f.txt")


class TestDeleteAllWithPrefix:
    async def test(
        self,
        file_repo: FileRepository,
        file_factory: FileFactory,
        folder_factory: FolderFactory,
        namespace: Namespace,
    ):
        ns_path = str(namespace.path)
        folder, *files = [
            await folder_factory(ns_path, "a/b/c"),
            await file_factory(ns_path, "a/b/c/f.txt"),
            await file_factory(ns_path, "a/b/c/d/f.txt"),
        ]
        await file_repo.delete_all_with_prefix(ns_path, prefix=f"{folder.path}/")
        assert await _exists_with_id(folder.id)
        assert not await _exists_with_id(files[0].id)
        assert not await _exists_with_id(files[1].id)


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


class TestGetById:
    async def test(self, file_repo: FileRepository, file: File):
        result = await file_repo.get_by_id(file.id)
        assert result == file

    async def test_when_file_does_not_exist(self, file_repo: FileRepository):
        file_id = str(uuid.uuid4())
        with pytest.raises(File.NotFound):
            await file_repo.get_by_id(file_id)


class TestGetByIdBatch:
    async def test(
        self, file_repo: FileRepository, file_factory: FileFactory, namespace: Namespace
    ):
        files = [await file_factory(namespace.path, path=f"{i}.txt") for i in range(3)]
        ids = [file.id for file in files]
        result = await file_repo.get_by_id_batch(ids)
        assert result == sorted(files, key=operator.attrgetter("path"))

    async def test_when_some_file_does_not_exist(
        self, file_repo: FileRepository, file: File,
    ):
        ids = [file.id, str(uuid.uuid4())]
        result = await file_repo.get_by_id_batch(ids)
        assert result == [file]


class TestGetByPath:
    async def test(self, file_repo: FileRepository, file: File):
        file_in_db = await file_repo.get_by_path(file.ns_path, file.path)
        assert file_in_db == file

    async def test_when_file_does_not_exist(
        self, namespace: Namespace, file_repo: FileRepository
    ):
        path = "f.txt"
        with pytest.raises(File.NotFound):
            await file_repo.get_by_path(namespace.path, path)


class TestGetByPathBatch:
    async def test(
        self, file_repo: FileRepository, file_factory: FileFactory, namespace: Namespace
    ):
        files = [await file_factory(namespace.path, f"{idx}.txt") for idx in range(3)]
        paths = [file.path for file in files]
        result = await file_repo.get_by_path_batch(namespace.path, paths)
        assert result == sorted(files, key=operator.attrgetter("path"))

    async def test_when_some_file_does_not_exist(
        self, file_repo: FileRepository, file: File,
    ):
        paths = [str(file.path), f"{uuid.uuid4()}.txt"]
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


class TestListByMediatypes:
    async def test_list_by_mediatypes(
        self, file_repo: FileRepository, file_factory: FileFactory, namespace: Namespace
    ):
        ns_path = namespace.path
        await file_factory(ns_path, "f.txt", mediatype="plain/text")
        jpg = await file_factory(ns_path, "jpgs/img.jpg", mediatype="image/jpeg")
        png = await file_factory(ns_path, "pngs/img.png", mediatype="image/png")
        mediatypes = ["image/jpeg", "image/png"]
        files = await file_repo.list_by_mediatypes(ns_path, mediatypes, offset=0)
        assert sorted(files, key=operator.attrgetter("mtime")) == [jpg, png]

    async def test_list_by_mediatypes_with_limit_offset(
        self, file_repo: FileRepository, file_factory: FileFactory, namespace: Namespace
    ):
        ns_path = namespace.path
        jpg = await file_factory(ns_path, "jpgs/img.jpg", mediatype="image/jpeg")
        png = await file_factory(ns_path, "pngs/img.png", mediatype="image/png")

        mediatypes = ["image/jpeg", "image/png"]
        files_a = await file_repo.list_by_mediatypes(
            ns_path, mediatypes, offset=0, limit=1,
        )
        files_b = await file_repo.list_by_mediatypes(
            ns_path, mediatypes, offset=1, limit=1,
        )
        assert len(files_a) == 1
        assert len(files_b) == 1
        actual = sorted([files_a[0], files_b[0]], key=operator.attrgetter("mtime"))
        assert actual == [jpg, png]


class TestListWithPrefix:
    async def test(
        self,
        file_repo: FileRepository,
        file_factory: FileFactory,
        folder_factory: FolderFactory,
        namespace: Namespace
    ):
        # GIVEN
        ns_path = namespace.path
        await folder_factory(ns_path, "home")
        await file_factory(ns_path, "home/f.txt")
        await folder_factory(ns_path, "home/folder")
        await file_factory(ns_path, "home/folder/f.txt")
        # WHEN
        files = await file_repo.list_with_prefix(ns_path, "home/")
        # THEN
        assert len(files) == 2
        assert files[0].path == "home/folder"
        assert files[1].path == "home/f.txt"

    async def test_listing_top_level(
        self,
        file_repo: FileRepository,
        file_factory: FileFactory,
        folder_factory: FolderFactory,
        namespace: Namespace
    ):
        # GIVEN
        ns_path = namespace.path
        await folder_factory(ns_path, "home")
        await file_factory(ns_path, "home/f.txt")
        await folder_factory(ns_path, "home/folder")
        await file_factory(ns_path, "home/folder/f.txt")
        # WHEN
        files = await file_repo.list_with_prefix(ns_path, "")
        # THEN
        assert len(files) == 1
        assert files[0].path == "home"

    async def test_listing_folder_containing_mount_points(
        self,
        file_repo: FileRepository,
        user_factory: UserFactory,
        namespace_factory: NamespaceFactory,
        folder_factory: FolderFactory,
        file_factory: FileFactory,
        mount_factory: MountFactory,
        namespace: Namespace,
    ):
        # GIVEN
        folder = await folder_factory(namespace.path, "Folder")
        await folder_factory(namespace.path, "Folder/Personal Folder")
        await file_factory(namespace.path, "Folder/f.txt")

        user_b = await user_factory()
        ns_b = await namespace_factory(user_b.username, owner_id=user_b.id)
        shared_folder = await folder_factory(ns_b.path, "Shared Folder")
        await mount_factory(shared_folder.id, folder.id, "Team Folder")

        # WHEN
        files = await file_repo.list_with_prefix(namespace.path, "Folder/")

        # THEN
        assert len(files) == 3
        assert files[0].path == "Folder/Personal Folder"
        assert files[1].path == "Folder/Team Folder"
        assert files[2].path == "Folder/f.txt"

    async def test_when_folder_does_not_exist(
        self, file_repo: FileRepository, namespace: Namespace
    ):
        # GIVEN
        ns_path = namespace.path
        # WHEN
        files = await file_repo.list_with_prefix(ns_path, "home/")
        # THEN
        assert len(files) == 0


class TestReplacePathPrefix:
    async def test(
        self, file_repo: FileRepository, file_factory: FileFactory, namespace: Namespace
    ):
        # GIVEN
        ns_path = namespace.path
        await file_factory(ns_path, "a/b/c/f.txt")
        await file_factory(ns_path, "a/b/c/d/f.txt")
        # WHEN
        await file_repo.replace_path_prefix(at=(ns_path, "a/b/c"), to=(ns_path, "d"))
        # THEN
        results = await file_repo.get_by_path_batch(ns_path, ["d/f.txt", "d/d/f.txt"])
        assert len(results) == 2
        assert results[0].path == "d/d/f.txt"
        assert results[1].path == "d/f.txt"

    @pytest.mark.database(transaction=True)
    async def test_changing_prefix_with_namesace(
        self,
        file_repo: FileRepository,
        file_factory: FileFactory,
        namespace_a: Namespace,
        namespace_b: Namespace,
    ):
        # GIVEN
        await file_factory(namespace_a.path, "a/b/f.txt")
        await file_factory(namespace_a.path, "a/b/c/f.txt")
        await file_factory(namespace_a.path, "a/b/c/d/f.txt")
        # WHEN
        await file_repo.replace_path_prefix(
            at=(namespace_a.path, "a/b/c"),
            to=(namespace_b.path, "d"),
        )
        # THEN
        assert await file_repo.exists_at_path(namespace_a.path, "a/b/f.txt")
        paths = ["d/f.txt", "d/d/f.txt"]
        results = await file_repo.get_by_path_batch(namespace_b.path, paths)
        assert len(results) == 2
        assert results[0].path == "d/d/f.txt"
        assert results[1].path == "d/f.txt"

    async def test_case_insensitiveness(
        self, file_repo: FileRepository, file_factory: FileFactory, namespace: Namespace
    ):
        # GIVEN
        ns_path = namespace.path
        await file_factory(ns_path, "A/b/C/f.txt")
        await file_factory(ns_path, "a/B/c/d/f.txt")
        # WHEN
        await file_repo.replace_path_prefix(at=(ns_path, "a/b/C"), to=(ns_path, "d"))
        # THEN
        results = await file_repo.get_by_path_batch(ns_path, ["d/f.txt", "d/d/f.txt"])
        assert len(results) == 2

    async def test_replacing_only_the_first_occurence(
        self, file_repo: FileRepository, file_factory: FileFactory, namespace: Namespace
    ):
        # GIVEN
        ns_path = namespace.path
        await file_factory(ns_path, "a/b/a/b/f.txt")
        # WHEN
        await file_repo.replace_path_prefix(at=(ns_path, "a/b"), to=(ns_path, "c"))
        # THEN
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
        with pytest.raises(File.AlreadyExists):
            await file_repo.save(file_to_save)


class TestSaveBatch:
    async def test(self, file_repo: FileRepository, namespace: Namespace):
        await file_repo.save_batch([
            File(
                id=SENTINEL_ID,
                name="folder",
                ns_path=namespace.path,
                path="folder",
                size=10,
                mtime=12.34,
                mediatype="application/directory",
            ),
            File(
                id=SENTINEL_ID,
                name="f.txt",
                ns_path=namespace.path,
                path="folder/f.txt",
                size=10,
                mtime=12.35,
                mediatype="plain/text",
            ),
        ])
        folder = await _get_by_path(namespace.path, "folder")
        assert folder.id != SENTINEL_ID
        assert folder.mediatype == "application/directory"

        file = await _get_by_path(namespace.path, "folder/f.txt")
        assert file.id != SENTINEL_ID
        assert file.mediatype == "plain/text"

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
        await file_repo.save_batch([file_to_save])

    async def test_when_empty_input(self, file_repo: FileRepository):
        await file_repo.save_batch([])


class TestUpdate:
    async def test(self, file_repo: FileRepository, file: File):
        file_update = FileUpdate(
            name=f".{file.name}",
            path=f".{file.path}",
        )
        updated_file = await file_repo.update(file, file_update)
        assert updated_file.name == f".{file.name}"
        assert updated_file.path == f".{file.path}"
        file_in_db = await _get_by_id(file.id)
        assert file_in_db == updated_file
