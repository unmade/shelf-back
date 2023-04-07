from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app import tasks
from app.app.files.domain import File, Path
from app.tasks import ErrorCode, RelocationPath

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from pytest import LogCaptureFixture

    from app.app.files.domain import AnyPath
    from app.tasks import FileTaskResult

pytestmark = [pytest.mark.usefixtures("celery_session_worker")]


@pytest.fixture(scope="module", autouse=True)
def setUp():
    with (
        mock.patch("app.tasks._create_database"),
        mock.patch("app.tasks._create_storage"),
    ):
        yield


def _make_file(ns_path: str, path: AnyPath):
    return File(
        id=uuid.uuid4(),
        ns_path=ns_path,
        name=Path(path).name,
        path=path,
        size=10,
        mediatype="plain/text",
    )


@pytest.mark.database(transaction=False)
def test_celery_works():
    task = tasks.ping.delay()
    assert task.get(timeout=1) == "pong"


class TestDeleteImmediatelyBatch:
    @pytest.fixture
    def delete_item(self):
        target = "app.app.files.usecases.NamespaceUseCase.delete_item"
        with mock.patch(target) as patch:
            yield patch

    def test(self, caplog: LogCaptureFixture, delete_item: MagicMock):
        ns_path = "admin"
        side_effect = [
            _make_file(ns_path, "Trash/a.txt"),
            File.NotFound,
            Exception,
            _make_file(ns_path, "Tras/f.txt"),
        ]
        delete_item.side_effect = side_effect

        paths = ["a.txt", "b.txt", "c.txt", "d.txt"]
        task = tasks.delete_immediately_batch.delay(ns_path, paths)

        results: list[FileTaskResult] = task.get(timeout=2)
        assert len(results) == 4

        assert results[0].file is not None
        assert results[0].file.path == side_effect[0].path

        assert results[1].file is None
        assert results[1].err_code == ErrorCode.file_not_found

        assert results[2].file is None
        assert results[2].err_code == ErrorCode.internal

        assert results[3].file is not None
        assert results[3].file.path == side_effect[3].path

        assert delete_item.await_count == 4

        msg = "Unexpectedly failed to delete a file"
        log_record = ("app.tasks", logging.ERROR, msg)
        assert caplog.record_tuples == [log_record]


class TestEmptyTrash:
    @pytest.fixture
    def empty_trash(self):
        target = "app.app.files.usecases.NamespaceUseCase.empty_trash"
        with mock.patch(target) as patch:
            yield patch

    async def test(self, empty_trash: MagicMock):
        ns_path = "admin"
        task = tasks.empty_trash.delay(ns_path)
        task.get(timeout=2)
        empty_trash.assert_awaited_once_with(ns_path)

    async def test_when_failed_unexpectedly(
        self, caplog: LogCaptureFixture, empty_trash: MagicMock
    ):
        ns_path = "admin"
        empty_trash.side_effect = Exception
        task = tasks.empty_trash.delay(ns_path)
        task.get(timeout=2)
        empty_trash.assert_awaited_once_with(ns_path)
        msg = "Unexpectedly failed to empty trash folder"
        log_record = ("app.tasks", logging.ERROR, msg)
        assert caplog.record_tuples == [log_record]


class TestMoveBatch:
    @pytest.fixture
    def move_item(self):
        target = "app.app.files.usecases.NamespaceUseCase.move_item"
        with mock.patch(target) as move_file_mock:
            yield move_file_mock

    def test(self, caplog: LogCaptureFixture, move_item: MagicMock):
        ns_path = "admin"
        move_item.side_effect = [
            _make_file(ns_path, "folder/a.txt"),
            File.MissingParent,
            Exception,
            _make_file(ns_path, "f.txt"),
        ]

        relocations = [
            RelocationPath(from_path="a.txt", to_path="folder/a.txt"),
            RelocationPath(from_path="b.txt", to_path="not_exists/b.txt"),
            RelocationPath(from_path="c.txt", to_path="e.txt"),
            RelocationPath(from_path="d.txt", to_path="f.txt"),
        ]

        task = tasks.move_batch.delay(ns_path, relocations)

        results: list[FileTaskResult] = task.get(timeout=2)
        assert len(results) == 4

        assert results[0].file is not None
        assert results[0].file.path == relocations[0].to_path

        assert results[1].file is None
        assert results[1].err_code == ErrorCode.missing_parent

        assert results[2].file is None
        assert results[2].err_code == ErrorCode.internal

        assert results[3].file is not None
        assert results[3].file.path == relocations[3].to_path

        assert move_item.await_count == 4

        msg = "Unexpectedly failed to move a file"
        log_record = ("app.tasks", logging.ERROR, msg)
        assert caplog.record_tuples == [log_record]


class TestMovetoTrashFile:
    @pytest.fixture
    def move_to_trash(self):
        target = "app.app.files.usecases.NamespaceUseCase.move_item_to_trash"
        with mock.patch(target) as move_file_mock:
            yield move_file_mock

    def test(self, caplog: LogCaptureFixture, move_to_trash: MagicMock):
        ns_path = "admin"
        side_effect = [
            _make_file(ns_path, "Trash/a.txt"),
            File.NotFound,
            Exception,
            _make_file(ns_path, "Tras/f.txt"),
        ]
        move_to_trash.side_effect = side_effect

        paths = ["a.txt", "b.txt", "c.txt", "d.txt"]
        task = tasks.move_to_trash_batch.delay(ns_path, paths)

        results: list[FileTaskResult] = task.get(timeout=2)
        assert len(results) == 4

        assert results[0].file is not None
        assert results[0].file.path == side_effect[0].path

        assert results[1].file is None
        assert results[1].err_code == ErrorCode.file_not_found

        assert results[2].file is None
        assert results[2].err_code == ErrorCode.internal

        assert results[3].file is not None
        assert results[3].file.path == side_effect[3].path

        assert move_to_trash.await_count == 4

        msg = "Unexpectedly failed to move file to trash"
        log_record = ("app.tasks", logging.ERROR, msg)
        assert caplog.record_tuples == [log_record]
