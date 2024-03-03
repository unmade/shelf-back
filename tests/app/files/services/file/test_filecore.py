from __future__ import annotations

import operator
import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.files.domain import File, Path, mediatypes
from app.app.files.services.file.filecore import ProcessFilePendingDeletionResult
from app.app.infrastructure.storage import DownloadBatchItem
from app.toolkit import chash, taskgroups
from app.toolkit.mediatypes import MediaType

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from app.app.files.domain import AnyPath, IFileContent, Namespace
    from app.app.files.services.file import FileCoreService
    from tests.fixtures.app.files import ContentFactory

    from ..conftest import (
        BookmarkFactory,
        FileFactory,
        FilePendingDeletionFactory,
        FolderFactory,
    )

pytestmark = [pytest.mark.anyio, pytest.mark.database]


def _make_file(
    ns_path: str, path: AnyPath, size: int = 10, mediatype: str = "plain/text"
) -> File:
    path = Path(path)
    return File(
        id=uuid.uuid4(),
        ns_path=ns_path,
        name=path.name,
        path=path,
        chash=chash.EMPTY_CONTENT_HASH,
        size=size,
        mediatype=mediatype,
    )


@mock.patch("app.app.files.services.file.filecore.chash.chash")
class TestCHashBatch:
    async def test(
        self,
        chash: MagicMock,
        filecore: FileCoreService,
        image_content: IFileContent,
    ):
        # GIVEN
        file_ids = [uuid.uuid4() for _ in range(3)]
        chahes = [uuid.uuid4().hex, "", uuid.uuid4().hex]
        chash.side_effect = chahes
        # WHEN
        with mock.patch.object(filecore.db.file, "set_chash_batch") as db_mock:
            async with filecore.chash_batch() as chasher:
                await chasher.add(file_ids[0], image_content.file)
                await chasher.add(file_ids[1], image_content.file)
                await chasher.add(file_ids[2], image_content.file)
        # THEN
        items = list(zip(file_ids, chahes, strict=False))
        db_mock.assert_awaited_once_with(items)
        chash.assert_has_calls([
            mock.call(image_content.file),
            mock.call(image_content.file),
            mock.call(image_content.file),
        ])


class TestCreateFile:
    async def test(
        self, filecore: FileCoreService, namespace: Namespace, content: IFileContent
    ):
        file = await filecore.create_file(namespace.path, "f.txt", content)
        assert file.name == "f.txt"
        assert file.path == "f.txt"
        assert file.size == content.size
        assert file.mediatype == 'text/plain'

    async def test_saving_an_image(
        self,
        filecore: FileCoreService,
        namespace: Namespace,
        image_content: IFileContent,
    ):
        content = image_content
        file = await filecore.create_file(namespace.path, "im.jpeg", content)
        assert file.mediatype == "image/jpeg"

    async def test_creating_missing_parents(
        self, filecore: FileCoreService, namespace: Namespace, content: IFileContent
    ):
        file = await filecore.create_file(namespace.path, "a/b/f.txt", content)
        assert file.name == "f.txt"
        assert file.path == "a/b/f.txt"

        paths = ["a", "a/b"]
        db = filecore.db
        a, b = await db.file.get_by_path_batch(namespace.path,  paths=paths)
        assert a.path == "a"
        assert b.path == "a/b"

    async def test_parents_size_is_updated(
        self, filecore: FileCoreService, namespace: Namespace, content: IFileContent
    ):
        await filecore.create_file(namespace.path, "a/b/f.txt", content)
        paths = [".", "a", "a/b"]
        db = filecore.db
        home, a, b = await db.file.get_by_path_batch(namespace.path, paths=paths)
        assert b.size == content.size
        assert a.size == b.size
        assert home.size == a.size

    @pytest.mark.slow
    @pytest.mark.database(transaction=True)
    async def test_saving_files_concurrently(
        self,
        filecore: FileCoreService,
        namespace: Namespace,
        content_factory: ContentFactory,
    ):
        CONCURRENCY = 50
        parent = Path("a/b/c")
        paths = [parent / str(name) for name in range(CONCURRENCY)]
        contents = [content_factory() for _ in range(CONCURRENCY)]

        await filecore.create_folder(namespace.path, parent)

        await taskgroups.gather(*(
            filecore.create_file(namespace.path, path, content)
            for path, content in zip(paths, contents, strict=True)
        ))

        db = filecore.db
        count = len(await db.file.get_by_path_batch(namespace.path, paths))
        assert count == CONCURRENCY

        home = await db.file.get_by_path(namespace.path, ".")
        assert home.size == sum(content.size for content in contents)

    async def test_when_file_path_already_taken(
        self, filecore: FileCoreService, namespace: Namespace, content: IFileContent
    ):
        await filecore.create_file(namespace.path, "f.txt", content)
        await filecore.create_file(namespace.path, "f.txt", content)

        db = filecore.db
        paths = ["f.txt", "f (1).txt"]
        f_1, f = await db.file.get_by_path_batch(namespace.path, paths)
        assert f.path == "f.txt"
        assert f_1.path == "f (1).txt"

    async def test_when_parent_path_is_file(
        self, filecore: FileCoreService, namespace: Namespace, content: IFileContent
    ):
        await filecore.create_file(namespace.path, "f.txt", content)
        with pytest.raises(File.NotADirectory):
            await filecore.create_file(namespace.path, "f.txt/f.txt", content)


class TestCreateFolder:
    async def test(self, filecore: FileCoreService, namespace: Namespace):
        folder = await filecore.create_folder(namespace.path, "New Folder")
        assert folder.name == "New Folder"

    async def test_nested_path(self, filecore: FileCoreService, namespace: Namespace):
        folder = await filecore.create_folder(namespace.path, "a/b/c/f")
        assert folder.path == "a/b/c/f"

    async def test_path_is_case_insensitive(
        self, filecore: FileCoreService, namespace: Namespace,
    ):
        b = await filecore.create_folder(namespace.path, "A/b")
        c = await filecore.create_folder(namespace.path, "a/B/c")

        assert b.path == "A/b"
        assert c.path == "A/b/c"

    async def test_when_folder_exists(
        self, filecore: FileCoreService, namespace: Namespace,
    ):
        folder = await filecore.create_folder(namespace.path, "New Folder")
        with pytest.raises(File.AlreadyExists):
            folder = await filecore.create_folder(namespace.path, folder.path)

    async def test_when_path_is_not_a_directory(
        self,
        filecore: FileCoreService,
        namespace: Namespace,
        file_factory: FileFactory,
    ):
        await file_factory(namespace.path, "f.txt")

        with pytest.raises(File.NotADirectory):
            await filecore.create_folder(namespace.path, "f.txt/folder")


class TestDelete:
    async def test_deleting_a_file(
        self, filecore: FileCoreService, namespace: Namespace, file: File
    ):
        # GIVEN
        ns_path = namespace.path
        # WHEN
        deleted_file = await filecore.delete(ns_path, file.path)
        # THEN
        assert deleted_file == file
        assert not await filecore.db.file.exists_with_id(ns_path, file.id)
        assert not await filecore.storage.exists(ns_path, file.path)

    async def test_deleting_a_folder(
        self,
        filecore: FileCoreService,
        file_factory: FileFactory,
        namespace: Namespace,
    ):
        # GIVEN
        ns_path = namespace.path
        await file_factory(ns_path, "a/b/c/f.txt")
        await file_factory(ns_path, "a/b/f (1).txt")
        await file_factory(ns_path, "a/c/f.txt")

        # WHEN
        await filecore.delete(ns_path, "a/b")

        # THEN
        # check folder deleted from DB with its content
        paths = ["a", "a/c", "a/b", "a/b/c", "a/b/c/f.txt", "a/b/f (1).txt"]
        files = await filecore.db.file.get_by_path_batch(ns_path, paths)
        assert len(files) == 2
        assert files[0].path == "a"
        assert files[1].path == "a/c"

        # check folder deleted from the storage
        assert not await filecore.storage.exists(ns_path, "a/b")

    async def test_updating_parent_size(
        self,
        filecore: FileCoreService,
        file_factory: FileFactory,
        namespace: Namespace,
    ):
        # GIVEN
        ns_path = namespace.path
        await file_factory(ns_path, "a/f.txt")
        await file_factory(ns_path, "a/b/c/d/f.txt")
        await file_factory(ns_path, "a/b/c/f.txt")

        # check parent sizes before deletion
        paths = ["a", "a/b"]
        a, b = await filecore.db.file.get_by_path_batch(ns_path, paths)
        assert a.size == 30
        assert b.size == 20

        # WHEN
        await filecore.delete(ns_path, "a/b/c")

        # THEN
        # check parents were updated
        a, b = await filecore.db.file.get_by_path_batch(ns_path, paths)
        assert a.size == 10
        assert b.size == 0

    async def test_when_file_is_bookmarked(
        self,
        filecore: FileCoreService,
        bookmark_factory: BookmarkFactory,
        namespace: Namespace,
        file: File,
    ):
        # GIVEN
        ns_path = namespace.path
        await bookmark_factory(namespace.owner_id, file.id)
        # WHEN
        await filecore.delete(ns_path, file.path)
        # THEN
        assert not await filecore.db.file.exists_with_id(ns_path, file.id)
        assert not await filecore.storage.exists(ns_path, file.path)

    async def test_when_file_does_not_exists(
        self, filecore: FileCoreService, namespace: Namespace
    ):
        with pytest.raises(File.NotFound):
            await filecore.delete(namespace.path, "f.txt")


class TestDeleteBatch:
    async def test(
        self,
        filecore: FileCoreService,
        file_factory: FileFactory,
        namespace: Namespace,
    ):
        # GIVEN
        ns_path = namespace.path
        await file_factory(ns_path, "a/b/c/f.txt")
        await file_factory(ns_path, "a/b/f (1).txt")
        await file_factory(ns_path, "a/c/f.txt")
        paths = ["a/b", "a/c/f.txt"]
        worker = cast(mock.MagicMock, filecore.worker)
        # WHEN
        await filecore.delete_batch(ns_path, paths)
        # THEN
        paths = [
            "a", "a/c", "a/c/f.txt", "a/b", "a/b/c", "a/b/c/f.txt", "a/b/f (1).txt"
        ]
        files = await filecore.db.file.get_by_path_batch(ns_path, paths)
        actual = {str(file.path) for file in files}
        expected = {"a", "a/c", "a/b/c", "a/b/c/f.txt", "a/b/f (1).txt"}
        assert actual == expected

        worker.enqueue.assert_awaited_once_with(
            "process_file_pending_deletion",
            ids=mock.ANY
        )
        # # check folder exists in the storage
        assert await filecore.storage.exists(ns_path, "a/b")
        assert await filecore.storage.exists(ns_path, "a/c/f.txt")


class TestDownload:
    async def test_on_file(self, filecore: FileCoreService, file: File):
        with mock.patch.object(filecore, "storage") as storage_mock:
            result = await filecore.download(file.id)
        storage_mock.download.assert_called_once_with(file.ns_path, file.path)
        assert result == (file, storage_mock.download.return_value)

    async def test_when_is_a_folder(self, filecore, folder: File):
        with mock.patch.object(filecore, "storage") as storage_mock:  # noqa: SIM117
            with pytest.raises(File.IsADirectory):
                await filecore.download(folder.id)
        storage_mock.downloaddir.assert_not_called()


class TestDownloadBatch:
    async def test(self, filecore: FileCoreService):
        # GIVEN
        items = [
            DownloadBatchItem(ns_path="admin", path="f.txt", is_dir=False),
            DownloadBatchItem(ns_path="admin", path="f.txt", is_dir=False),
        ]
        # WHEN
        with mock.patch.object(filecore, "storage") as storage_mock:
            result = filecore.download_batch(items)
        # THEN
        storage_mock.download_batch.assert_called_once_with(items)
        assert result == storage_mock.download_batch.return_value


class TestDownloadFolder:
    async def test(self, filecore: FileCoreService, file: File):
        with mock.patch.object(filecore, "storage") as storage_mock:
            result = filecore.download_folder(file.ns_path, file.path)
        storage_mock.downloaddir.assert_called_once_with(file.ns_path, file.path)
        assert result == storage_mock.downloaddir.return_value


class TestEmptyFolder:
    async def test(
        self,
        filecore: FileCoreService,
        file_factory: FileFactory,
        namespace: Namespace,
    ):
        # GIVEN
        ns_path = namespace.path
        file_a = await file_factory(ns_path, "Folder/f.txt")
        file_b = await file_factory(ns_path, "Folder/a/f.txt")
        # WHEN
        await filecore.empty_folder(ns_path, "Folder")
        # THEN
        assert not await filecore.db.file.exists_with_id(ns_path, file_a.id)
        assert not await filecore.db.file.exists_with_id(ns_path, file_b.id)
        assert not await filecore.storage.exists(ns_path, file_a.path)
        assert not await filecore.storage.exists(ns_path, file_b.path)

    async def test_updating_folder_size(
        self,
        filecore: FileCoreService,
        file_factory: FileFactory,
        namespace: Namespace,
    ):
        # GIVEN
        ns_path = namespace.path
        await file_factory(ns_path, "Outer Folder/Inner Folder/f.txt")

        # check parent size before emptying the trash
        paths = ["outer folder", "outer folder/inner folder"]
        outer, inner = await filecore.db.file.get_by_path_batch(ns_path, paths)
        assert outer.size > 0
        assert inner.size > 0

        # WHEN
        await filecore.empty_folder(ns_path, "outer folder/inner folder")

        # THEN
        paths = ["outer folder", "outer folder/inner folder"]
        outer, inner = await filecore.db.file.get_by_path_batch(ns_path, paths)
        assert outer.size == 0
        assert inner.size == 0

    async def test_when_folder_is_empty(self, filecore: FileCoreService, folder: File):
        with (
            mock.patch.object(filecore.db.file, "delete_all_with_prefix") as db_mock,
            mock.patch.object(filecore.storage, "emptydir") as storage_mock,
        ):
            await filecore.empty_folder(folder.ns_path, folder.path)

        db_mock.assert_not_awaited()
        storage_mock.assert_not_awaited()


class TestExistsWithID:
    async def test(self, filecore: FileCoreService):
        # GIVEN
        ns_path, file_id = "admin", uuid.uuid4()
        # WHEN
        with mock.patch.object(filecore, "db", autospec=filecore.db) as db:
            result = await filecore.exists_with_id(ns_path, file_id)
        # THEN
        assert result == db.file.exists_with_id.return_value
        db.file.exists_with_id.assert_awaited_once_with(ns_path, file_id)


class TestExistsAtPath:
    async def test(self, filecore: FileCoreService):
        # GIVEN
        ns_path, path = "admin", "home"
        # WHEN
        with mock.patch.object(filecore, "db", autospec=filecore.db) as db:
            result = await filecore.exists_at_path(ns_path, path)
        # THEN
        assert result == db.file.exists_at_path.return_value
        db.file.exists_at_path.assert_awaited_once_with(ns_path, path)


class TestGetAvailablePath:
    @pytest.mark.parametrize(["name", "expected_name"], [
        ("f.txt", "f (1).txt"),
        ("f.tar.gz", "f (1).tar.gz"),
        ("f (1).tar.gz", "f (1) (1).tar.gz"),
    ])
    async def test(
        self,
        filecore: FileCoreService,
        file_factory: FileFactory,
        namespace: Namespace,
        name: str,
        expected_name: str,
    ):
        # GIVEN
        ns_path = namespace.path
        await file_factory(ns_path, f"a/b/{name}")
        # WHEN
        actual = await filecore.get_available_path(ns_path, f"a/b/{name}")
        # WHEN
        assert actual == f"a/b/{expected_name}"

    async def test_available_path_is_sequential(
        self,
        filecore: FileCoreService,
        file_factory: FileFactory,
        namespace: Namespace,
    ):
        # GIVEN
        ns_path = namespace.path
        await file_factory(ns_path, "f.tar.gz")
        await file_factory(ns_path, "f (1).tar.gz")
        # WHEN
        path = await filecore.get_available_path(ns_path, "f.tar.gz")
        # THEN
        assert path == "f (2).tar.gz"

    async def test_case_insensitiveness(
        self,
        filecore: FileCoreService,
        file_factory: FileFactory,
        namespace: Namespace,
    ):
        # GIVEN
        ns_path = namespace.path
        await file_factory(ns_path, "F.TAR.GZ")
        # WHEN
        path = await filecore.get_available_path(ns_path, "f.tar.gz")
        # THEN
        assert path == "f (1).tar.gz"

    async def test_returning_path_as_is(
        self, filecore: FileCoreService, namespace: Namespace
    ):
        next_path = await filecore.get_available_path(namespace.path, "f.txt")
        assert next_path == "f.txt"


class TestGetByCHashBatch:
    async def test(self, filecore: FileCoreService):
        # GIVEN
        chashes = [uuid.uuid4().hex for _ in range(3)]
        # WHEN
        with mock.patch.object(filecore, "db", autospec=filecore.db) as db:
            result = await filecore.get_by_chash_batch(chashes)
        # THEN
        assert result == db.file.get_by_chash_batch.return_value
        db.file.get_by_chash_batch.assert_awaited_once_with(chashes)


class TestGetById:
    async def test(self, filecore: FileCoreService):
        # GIVEN
        file_id = uuid.uuid4()
        # WHEN
        with mock.patch.object(filecore, "db", autospec=filecore.db) as db:
            result = await filecore.get_by_id(file_id)
        # THEN
        assert result == db.file.get_by_id.return_value
        db.file.get_by_id.assert_awaited_once_with(file_id)


class TestGetByIDBatch:
    async def test(self, filecore: FileCoreService):
        # GIVEN
        ids = [uuid.uuid4(), uuid.uuid4()]
        # WHEN
        with mock.patch.object(filecore, "db", autospec=filecore.db) as db:
            result = await filecore.get_by_id_batch(ids=ids)
        # THEN
        assert result == db.file.get_by_id_batch.return_value
        db.file.get_by_id_batch.assert_awaited_once_with(ids)


class TestGetByPath:
    async def test(self, filecore: FileCoreService):
        # GIVEN
        ns_path, path = "admin", "home"
        # WHEN
        with mock.patch.object(filecore, "db", autospec=filecore.db) as db:
            result = await filecore.get_by_path(ns_path, path)
        # THEN
        assert result == db.file.get_by_path.return_value
        db.file.get_by_path.assert_awaited_once_with(ns_path, path)


class TestIterFiles:
    async def test(
        self,
        filecore: FileCoreService,
        file_factory: FileFactory,
        namespace: Namespace,
        image_content: IFileContent,
    ):
        # GIVEN
        ns_path = str(namespace.path)
        await file_factory(ns_path, "plain.txt")
        jpg_1 = await file_factory(ns_path, "img (1).jpg", content=image_content)
        jpg_2 = await file_factory(ns_path, "img (2).jpg", content=image_content)
        mediatypes = ["image/jpeg"]
        # WHEN
        batches = filecore.iter_files(
            ns_path, included_mediatypes=mediatypes, batch_size=1
        )
        result = [files async for files in batches]
        # THEN
        assert len(result) == 2
        actual = [*result[0], *result[1]]
        assert sorted(actual, key=operator.attrgetter("modified_at")) == [jpg_1, jpg_2]

    async def test_when_no_files(
        self, filecore: FileCoreService, namespace: Namespace
    ):
        # GIVEN
        ns_path = namespace.path
        mediatypes = ["image/jpeg", "image/png"]
        # WHEN
        batches = filecore.iter_files(
            ns_path, included_mediatypes=mediatypes, batch_size=1
        )
        result = [files async for files in batches]
        # THEN
        assert result == []


class TestListFolder:
    async def test(
        self,
        filecore: FileCoreService,
        file_factory: FileFactory,
        folder_factory: FolderFactory,
        namespace: Namespace,
    ):
        # GIVEN
        ns_path = namespace.path
        await folder_factory(ns_path, "home")
        await file_factory(ns_path, "home/f.txt")
        # WHEN
        files = await filecore.list_folder(ns_path, "home")
        # THEN
        assert len(files) == 1
        assert files[0].path == "home/f.txt"

    async def test_listing_top_level(
        self,
        filecore: FileCoreService,
        file_factory: FileFactory,
        folder_factory: FolderFactory,
        namespace: Namespace,
    ):
        # GIVEN
        ns_path = namespace.path
        await folder_factory(ns_path, "home")
        await file_factory(ns_path, "home/f.txt")
        # WHEN
        files = await filecore.list_folder(ns_path, ".")
        # THEN
        assert len(files) == 3
        assert files[0].path == "."
        assert files[1].path == "home"
        assert files[2].path == "Trash"

    async def test_when_path_is_a_file(self, filecore: FileCoreService, file: File):
        with pytest.raises(File.NotADirectory):
            await filecore.list_folder(file.ns_path, file.path)

    async def test_when_path_does_not_exist(
        self, filecore: FileCoreService, namespace: Namespace
    ):
        with pytest.raises(File.NotFound):
            await filecore.list_folder(namespace.path, "home")


class TestMove:
    async def test_moving_a_file(
        self,
        filecore: FileCoreService,
        file_factory: FileFactory,
        namespace: Namespace,
    ):
        # GIVEN
        ns_path = namespace.path
        file = await file_factory(namespace.path, "f.txt")
        # WHEN
        moved_file = await filecore.move(
            at=(ns_path, file.path),
            to=(ns_path, ".f.txt"),
        )
        # THEN
        assert moved_file.name == ".f.txt"
        assert moved_file.path == ".f.txt"
        assert await filecore.storage.exists(namespace.path, ".f.txt")
        assert await filecore.db.file.exists_at_path(namespace.path, ".f.txt")

    async def test_moving_a_file_beetwen_namespaces(
        self,
        filecore: FileCoreService,
        file_factory: FileFactory,
        namespace_a: Namespace,
        namespace_b: Namespace,
    ):
        # GIVEN
        file = await file_factory(namespace_a.path, "f.txt")
        # WHEN
        result = await filecore.move(
            at=(namespace_a.path, file.path),
            to=(namespace_b.path, file.path),
        )
        # THEN
        assert result.ns_path == namespace_b.path
        assert result.path == "f.txt"
        assert not await filecore.storage.exists(namespace_a.path, "f.txt")
        assert not await filecore.db.file.exists_at_path(namespace_a.path, "f.txt")
        assert await filecore.db.file.exists_at_path(namespace_b.path, "f.txt")

    async def test_moving_a_folder(
        self,
        filecore: FileCoreService,
        file_factory: FileFactory,
        namespace: Namespace,
    ):
        # GIVEN
        ns_path = namespace.path
        await file_factory(ns_path, path="a/b/f.txt")

        # WHEN: rename folder 'b' to 'c'
        moved_file = await filecore.move(
            at=(ns_path, "a/b"),
            to=(ns_path, "a/c"),
        )

        # THEN
        assert moved_file.name == "c"
        assert moved_file.path == "a/c"

        assert not await filecore.storage.exists(ns_path, "a/b")
        assert not await filecore.db.file.exists_at_path(ns_path, "a/b")
        assert not await filecore.storage.exists(ns_path, "a/b/f.txt")
        assert not await filecore.db.file.exists_at_path(ns_path, "a/b/f.txt")

        assert await filecore.storage.exists(ns_path, "a/c")
        assert await filecore.db.file.exists_at_path(ns_path, "a/c")
        assert await filecore.storage.exists(ns_path, "a/c/f.txt")
        assert await filecore.db.file.exists_at_path(ns_path, "a/c/f.txt")

    async def test_moving_a_folder_beetwen_namespaces(
        self,
        filecore: FileCoreService,
        file_factory: FileFactory,
        folder_factory: FolderFactory,
        namespace_a: Namespace,
        namespace_b: Namespace,
    ):
        # GIVEN
        ns_path = namespace_a.path
        await file_factory(ns_path, path="a/b/f.txt")

        await folder_factory(namespace_b.path, "a")

        # WHEN: move folder 'b' to folder 'a' under name 'c'
        moved_file = await filecore.move(
            at=(namespace_a.path, "a/b"),
            to=(namespace_b.path, "a/c"),
        )

        # THEN
        assert moved_file.name == "c"
        assert moved_file.path == "a/c"

        assert not await filecore.storage.exists(ns_path, "a/b")
        assert not await filecore.db.file.exists_at_path(ns_path, "a/b")
        assert not await filecore.storage.exists(ns_path, "a/b/f.txt")
        assert not await filecore.db.file.exists_at_path(ns_path, "a/b/f.txt")

        assert await filecore.storage.exists(namespace_b.path, "a/c")
        assert await filecore.db.file.exists_at_path(namespace_b.path, "a/c")
        assert await filecore.storage.exists(namespace_b.path, "a/c/f.txt")
        assert await filecore.db.file.exists_at_path(namespace_b.path, "a/c/f.txt")

    async def test_updating_parents_size(
        self,
        filecore: FileCoreService,
        file_factory: FileFactory,
        namespace: Namespace,
    ):
        # GIVEN
        await file_factory(namespace.path, "a/b/f.txt")
        await file_factory(namespace.path, "a/b/c/x.txt")
        await file_factory(namespace.path, "a/b/c/y.txt")
        await file_factory(namespace.path, "a/g/z.txt")
        # WHEN
        await filecore.move(
            at=(namespace.path, "a/b/c"),
            to=(namespace.path, "a/g/c"),
        )
        # THEN
        paths = [".", "a", "a/b", "a/g"]
        h, a, b, g = await filecore.db.file.get_by_path_batch(namespace.path, paths)
        assert h.size == 40
        assert a.size == 40
        assert b.size == 10
        assert g.size == 30

    async def test_case_sensitive_renaming(
        self,
        filecore: FileCoreService,
        file_factory: FileFactory,
        namespace: Namespace,
    ):
        # GIVEN
        ns_path = namespace.path
        await file_factory(namespace.path, path="file.txt")
        # WHEN
        moved_file = await filecore.move(
            at=(ns_path, "file.txt"),
            to=(ns_path, "File.txt"),
        )
        # THEN
        assert moved_file.name == "File.txt"
        assert str(moved_file.path) == "File.txt"
        assert await filecore.storage.exists(ns_path, "File.txt")
        assert await filecore.db.file.exists_at_path(ns_path, "File.txt")

    async def test_case_insensitiveness(
        self,
        filecore: FileCoreService,
        file_factory: FileFactory,
        folder_factory: FolderFactory,
        namespace: Namespace,
    ):
        # GIVEN
        ns_path = namespace.path
        await folder_factory(namespace.path, "a")
        await folder_factory(namespace.path, "a/C")
        await folder_factory(namespace.path, "a/B")
        await folder_factory(namespace.path, "a/B/C")
        await file_factory(namespace.path, "a/B/C/f.txt")
        # WHEN: move file from 'a/B' to folder 'a/C'
        moved_file = await filecore.move(
            at=(ns_path, "a/b"),
            to=(ns_path, "a/c/B"),
        )
        # THEN
        assert moved_file.name == "B"
        assert str(moved_file.path) == "a/C/B"

        # nested files preserves casing
        f = await filecore.db.file.get_by_path(ns_path, "a/c/b/c/f.txt")
        assert f.name == "f.txt"
        assert str(f.path) == "a/C/B/C/f.txt"

    async def test_when_path_does_not_exist(
        self, filecore: FileCoreService, namespace: Namespace
    ):
        with pytest.raises(File.NotFound):
            await filecore.move(
                at=(namespace.path, "f.txt"),
                to=(namespace.path, "a/f.txt"),
            )

    async def test_when_next_path_is_taken(
        self,
        filecore: FileCoreService,
        file_factory: FileFactory,
        namespace: Namespace,
    ):
        await file_factory(namespace.path, "a/b/x.txt")
        await file_factory(namespace.path, "a/c/y.txt")
        with pytest.raises(File.AlreadyExists):
            await filecore.move(
                at=(namespace.path, "a/b"),
                to=(namespace.path, "a/c"),
            )

    async def test_when_next_path_parent_is_missing(
        self,
        filecore: FileCoreService,
        file_factory: FileFactory,
        namespace: Namespace,
    ):
        await file_factory(namespace.path, "f.txt")
        with pytest.raises(File.MissingParent):
            await filecore.move(
                at=(namespace.path, "f.txt"),
                to=(namespace.path, "a/f.txt"),
            )

    async def test_when_next_path_is_not_a_folder(
        self,
        filecore: FileCoreService,
        file_factory: FileFactory,
        namespace: Namespace,
    ):
        await file_factory(namespace.path, "x.txt")
        await file_factory(namespace.path, "y")
        with pytest.raises(File.NotADirectory):
            await filecore.move(
                at=(namespace.path, "x.txt"),
                to=(namespace.path, "y/x.txt"),
            )

    @pytest.mark.parametrize(["a", "b"], [
        ("a/b", "a/b/b"),
        ("a/B", "A/b/B"),
    ])
    async def test_when_moving_to_itself(
        self,
        filecore: FileCoreService,
        namespace: Namespace,
        a: str,
        b: str,
    ):
        with pytest.raises(File.MalformedPath) as excinfo:
            await filecore.move(at=(namespace.path, a), to=(namespace.path, b))
        assert str(excinfo.value) == "Can't move to itself."


class TestProcessFileDeletion:
    async def test_files_are_deleted(
        self,
        filecore: FileCoreService,
        file_factory: FileFactory,
        file_pending_deletion_factory: FilePendingDeletionFactory,
        namespace_a: Namespace,
        namespace_b: Namespace,
    ):
        # GIVEN
        storage = filecore.storage

        files = [
            await file_factory(namespace_a.path),
            await file_factory(namespace_a.path),
            await file_factory(namespace_b.path),
            await file_factory(namespace_b.path),
        ]

        file_deletions = []
        for file in files:
            file_deletions.append(
                await file_pending_deletion_factory(
                    file.ns_path, file.path, mediatype=MediaType.PLAIN_TEXT
                )
            )

        ids = [item.id for item in file_deletions]

        # WHEN
        result = await filecore.process_file_pending_deletion(ids)

        # THEN
        assert result == [
            ProcessFilePendingDeletionResult(
                ns_path=item.ns_path,
                path=item.path,
                chash=item.chash,
                mediatype=item.mediatype,
            )
            for item in file_deletions
        ]

        for item in file_deletions:
            assert not await storage.exists(item.ns_path, item.path)

    async def test_folders_are_deleted_with_its_children(
        self,
        filecore: FileCoreService,
        file_factory: FileFactory,
        folder_factory: FolderFactory,
        file_pending_deletion_factory: FilePendingDeletionFactory,
        namespace_a: Namespace,
        namespace_b: Namespace,
    ):
        # GIVEN
        db = filecore.db
        storage = filecore.storage

        folders = [
            await folder_factory(namespace_a.path),
            await folder_factory(namespace_a.path),
            await folder_factory(namespace_b.path),
            await folder_factory(namespace_b.path),
        ]

        children = []
        folder_deletions = []
        for folder in folders:
            folder_deletions.append(
                await file_pending_deletion_factory(
                    folder.ns_path, folder.path, mediatype=MediaType.FOLDER
                ),
            )
            path = folder.path / uuid.uuid4().hex
            children.append(
                await file_factory(folder.ns_path, path),
           )

        ids = [item.id for item in folder_deletions]

        # WHEN
        result = await filecore.process_file_pending_deletion(ids)

        # THEN
        actual = sorted(result, key=operator.attrgetter("path"))
        expected = sorted(
            (
                ProcessFilePendingDeletionResult(
                    ns_path=item.ns_path,
                    path=str(item.path),
                    chash=item.chash,
                    mediatype=item.mediatype,
                )
                for item in folder_deletions + children
            ),
            key=operator.attrgetter("path"),
        )
        assert actual == expected

        # check folder children deleted
        for item in folder_deletions:
            assert not await db.file.list_with_prefix(item.ns_path, f"{item.path}/")
            assert not [file async for file in storage.iterdir(item.ns_path, item.path)]


class TestReindex:
    async def test_creating_missing_files(
        self,
        filecore: FileCoreService,
        namespace: Namespace,
        content: IFileContent,
        image_content: IFileContent,
    ):
        # GIVEN
        db = filecore.db
        storage = filecore.storage

        # these files exist in the storage, but not in the database
        await storage.makedirs(namespace.path, "a")
        await storage.makedirs(namespace.path, "b")
        await storage.save(namespace.path, "b/f.txt", content=content)
        await storage.save(namespace.path, "im.jpeg", content=image_content)

        # WHEN
        await filecore.reindex(namespace.path, ".")

        # THEN
        # ensure home size is correct
        home = await db.file.get_by_path(namespace.path, ".")
        assert home.size == 1668

        # ensure missing files in the database has been created
        paths = ["a", "b", "b/f.txt", "im.jpeg"]
        a, b, f, i = await db.file.get_by_path_batch(namespace.path, paths=paths)
        assert a.is_folder()
        assert a.size == 0
        assert b.is_folder()
        assert b.size == content.size
        assert f.size == content.size
        assert f.mediatype == "text/plain"
        assert i.mediatype == "image/jpeg"
        assert i.size == image_content.size

    async def test_removing_dangling_files(
        self,
        filecore: FileCoreService,
        namespace: Namespace,
    ):
        # GIVEN
        db = filecore.db

        # these files exist in the database, but not in the storage
        await db.file.save_batch([
            _make_file(namespace.path, "c", size=32, mediatype=mediatypes.FOLDER),
            _make_file(namespace.path, "c/d", size=32, mediatype=mediatypes.FOLDER),
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
        file_factory: FileFactory,
        namespace: Namespace,
    ):
        # GIVEN
        db = filecore.db
        file = await file_factory(namespace.path, path="e/g/f.txt")

        # WHEN
        await filecore.reindex(namespace.path, "e")

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
        with pytest.raises(File.NotADirectory):
            await filecore.reindex(namespace.path, "a")

    async def test_when_path_is_a_file_in_the_storage(
        self,
        filecore: FileCoreService,
        namespace: Namespace,
        content: IFileContent,
    ):
        await filecore.storage.makedirs(namespace.path, ".")
        await filecore.storage.save(namespace.path, "a", content=content)
        with pytest.raises(File.NotADirectory):
            await filecore.reindex(namespace.path, "a")
        assert not await filecore.db.file.exists_at_path(namespace.path, "a")
