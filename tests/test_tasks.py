from __future__ import annotations

import logging
import os.path
import uuid
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app import crud, errors, tasks
from app.entities import RelocationPath

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from pytest import LogCaptureFixture

    from app.entities import FileTaskResult, Namespace
    from app.typedefs import DBClient
    from tests.factories import FileFactory

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.database(transaction=True),
    pytest.mark.usefixtures("celery_session_worker"),
]


def _make_file(ns_path: str, path: str):
    from app.domain.entities import File
    return File(
        id=uuid.uuid4(),
        ns_path=ns_path,
        name=os.path.basename(path),
        path=path,
        size=10,
        mediatype="plain/text",
    )


@pytest.mark.database(transaction=False)
def test_celery_works():
    task = tasks.ping.delay()
    assert task.get(timeout=1) == "pong"


async def test_delete_immediately_batch(
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path, path="x.txt")

    task = tasks.delete_immediately_batch.delay(namespace, [file.path, "y.txt"])
    result: list[FileTaskResult] = task.get(timeout=2)

    assert len(result) == 2
    assert result[0].file == file
    assert result[0].err_code is None

    assert result[1].file is None
    assert result[1].err_code == errors.ErrorCode.file_not_found


async def test_delete_immediately_batch_but_deletefails_with_an_error(
    namespace: Namespace,
):
    task = tasks.delete_immediately_batch.delay(namespace, ["x.txt", "y.txt"])
    result: list[FileTaskResult] = task.get(timeout=2)

    assert len(result) == 2
    assert result[0].file is None
    assert result[0].err_code == errors.ErrorCode.file_not_found

    assert result[1].file is None
    assert result[1].err_code == errors.ErrorCode.file_not_found


async def test_delete_immediately_batch_but_delete_fails_with_exception(
    caplog: LogCaptureFixture,
    namespace: Namespace,
):
    task = tasks.delete_immediately_batch.delay(namespace, ["f.txt"])
    func = "app.actions.delete_immediately"
    with mock.patch(func, side_effect=Exception) as delete_mock:
        result: list[FileTaskResult] = task.get(timeout=2)

    assert delete_mock.called

    assert result[0].file is None
    assert result[0].err_code == errors.ErrorCode.internal

    log_record = "app.tasks", logging.ERROR, "Unexpectedly failed to delete a file"
    assert caplog.record_tuples == [log_record]


async def test_empty_trash(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    paths = ["Trash/f.txt", "Trash/folder/x.txt", "Trash/folder/y.txt"]
    for path in paths:
        await file_factory(namespace.path, path)

    task = tasks.empty_trash.delay(namespace)
    result = task.get(timeout=2)

    assert result is None

    trash = await crud.file.get(db_client, namespace.path, "Trash")
    assert trash.size == 0

    for path in paths:
        assert not await crud.file.exists(db_client, namespace.path, path)


class TestMoveBatch:
    @pytest.fixture(autouse=True)
    def setUp(self):
        with (
            mock.patch("app.tasks._create_database"),
            mock.patch("app.tasks._create_storage"),
        ):
            yield

    @pytest.fixture
    def move_file(self):
        target = "app.app.services.NamespaceService.move_file"
        with mock.patch(target) as move_file_mock:
            yield move_file_mock

    def test(
        self, caplog: LogCaptureFixture, namespace: Namespace, move_file: MagicMock
    ):
        move_file.side_effect = [
            _make_file(str(namespace.path), "folder/a.txt"),
            errors.MissingParent,
            Exception,
            _make_file(str(namespace.path), "f.txt"),
        ]

        relocations = [
            RelocationPath(from_path="a.txt", to_path="folder/a.txt"),
            RelocationPath(from_path="b.txt", to_path="not_exists/b.txt"),
            RelocationPath(from_path="c.txt", to_path="e.txt"),
            RelocationPath(from_path="d.txt", to_path="f.txt"),
        ]

        task = tasks.move_batch.delay(namespace.path, relocations)

        results: list[FileTaskResult] = task.get(timeout=2)
        assert len(results) == 4

        assert results[0].file is not None
        assert results[0].file.path == relocations[0].to_path

        assert results[1].file is None
        assert results[1].err_code == errors.ErrorCode.missing_parent

        assert results[2].file is None
        assert results[2].err_code == errors.ErrorCode.internal

        assert results[3].file is not None
        assert results[3].file.path == relocations[3].to_path

        assert move_file.await_count == 4

        msg = "Unexpectedly failed to move file"
        log_record = ("app.tasks", logging.ERROR, msg)
        assert caplog.record_tuples == [log_record]


class TestMovetoTrashFile:
    @pytest.fixture(autouse=True)
    def setUp(self):
        with (
            mock.patch("app.tasks._create_database"),
            mock.patch("app.tasks._create_storage"),
        ):
            yield

    @pytest.fixture
    def move_to_trash(self):
        target = "app.app.services.NamespaceService.move_file_to_trash"
        with mock.patch(target) as move_file_mock:
            yield move_file_mock

    def test(
        self, caplog: LogCaptureFixture, namespace: Namespace, move_to_trash: MagicMock
    ):
        side_effect = [
            _make_file(str(namespace.path), "Trash/a.txt"),
            errors.FileNotFound,
            Exception,
            _make_file(str(namespace.path), "Tras/f.txt"),
        ]
        move_to_trash.side_effect = side_effect

        paths = ["a.txt", "b.txt", "c.txt", "d.txt"]
        task = tasks.move_to_trash_batch.delay(namespace.path, paths)

        results: list[FileTaskResult] = task.get(timeout=2)
        assert len(results) == 4

        assert results[0].file is not None
        assert results[0].file.path == side_effect[0].path

        assert results[1].file is None
        assert results[1].err_code == errors.ErrorCode.file_not_found

        assert results[2].file is None
        assert results[2].err_code == errors.ErrorCode.internal

        assert results[3].file is not None
        assert results[3].file.path == side_effect[3].path

        assert move_to_trash.await_count == 4

        msg = "Unexpectedly failed to move file to trash"
        log_record = ("app.tasks", logging.ERROR, msg)
        assert caplog.record_tuples == [log_record]
