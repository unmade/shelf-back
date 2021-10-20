from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app import crud, errors, tasks
from app.entities import RelocationPath

if TYPE_CHECKING:
    from pytest import LogCaptureFixture

    from app.entities import FileTaskResult, Namespace
    from app.typedefs import DBPool
    from tests.factories import FileFactory


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.database(transaction=True),
    pytest.mark.usefixtures("celery_session_worker"),
]


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
    db_pool: DBPool,
    namespace: Namespace,
    file_factory: FileFactory,
):
    paths = ["Trash/f.txt", "Trash/folder/x.txt", "Trash/folder/y.txt"]
    for path in paths:
        await file_factory(namespace.path, path)

    task = tasks.empty_trash.delay(namespace)
    result = task.get(timeout=2)

    assert result is None

    trash = await crud.file.get(db_pool, namespace.path, "Trash")
    assert trash.size == 0

    for path in paths:
        assert not await crud.file.exists(db_pool, namespace.path, path)


async def test_move_batch(namespace: Namespace, file_factory: FileFactory):
    await file_factory(namespace.path, path="folder/a")
    files = [await file_factory(namespace.path) for _ in range(2)]
    relocations = [
        RelocationPath(from_path=files[0].path, to_path=f"folder/{files[0].path}"),
        RelocationPath(from_path=files[1].path, to_path=f"not_exists/{files[1].path}"),
    ]

    task = tasks.move_batch.delay(namespace, relocations)
    results: list[FileTaskResult] = task.get(timeout=2)
    assert len(results) == 2

    assert results[0].file is not None
    assert results[0].file.path == relocations[0].to_path

    assert results[1].file is None
    assert results[1].err_code == errors.ErrorCode.missing_parent


async def test_move_batch_but_move_fails_with_exception(
    caplog: LogCaptureFixture,
    namespace: Namespace,
    file_factory: FileFactory,
):
    files = [await file_factory(namespace.path) for _ in range(2)]
    relocations = [
        RelocationPath(from_path=files[0].path, to_path=f".{files[0].path}"),
        RelocationPath(from_path=files[1].path, to_path=f".{files[1].path}"),
    ]

    task = tasks.move_batch.delay(namespace, relocations)
    with mock.patch("app.actions.move", side_effect=Exception) as move_mock:
        results: list[FileTaskResult] = task.get(timeout=2)

    assert move_mock.call_count == 2

    assert len(results) == 2

    assert results[0].file is None
    assert results[0].err_code == errors.ErrorCode.internal

    assert results[1].file is None
    assert results[1].err_code == errors.ErrorCode.internal

    log_record = ("app.tasks", logging.ERROR, "Unexpectedly failed to move file")
    assert caplog.record_tuples == [log_record, log_record]


async def test_move_to_trash_batch(namespace: Namespace, file_factory: FileFactory):
    files = [await file_factory(namespace.path) for _ in range(2)]
    paths = [files[0].path, "file_not_exist.txt"]

    task = tasks.move_to_trash_batch.delay(namespace, paths)
    results: list[FileTaskResult] = task.get(timeout=2)

    assert len(results) == 2

    assert results[0].file is not None
    assert results[0].file.path == f"Trash/{paths[0]}"

    assert results[1].file is None
    assert results[1].err_code == errors.ErrorCode.file_not_found


async def test_move_to_trash_batch_but_move_fails_with_exception(
    caplog: LogCaptureFixture,
    namespace: Namespace,
    file_factory: FileFactory,
):
    files = [await file_factory(namespace.path) for _ in range(2)]
    paths = [files[0].path, "file_not_exist.txt"]

    task = tasks.move_to_trash_batch.delay(namespace, paths)
    with mock.patch("app.actions.move_to_trash", side_effect=Exception) as move_mock:
        results: list[FileTaskResult] = task.get(timeout=2)

    assert move_mock.call_count == 2

    assert len(results) == 2

    assert results[0].file is None
    assert results[0].err_code == errors.ErrorCode.internal
    assert results[1].file is None
    assert results[1].err_code == errors.ErrorCode.internal

    log_record = "app.tasks", logging.ERROR, "Unexpectedly failed to move file to trash"
    assert caplog.record_tuples == [log_record, log_record]
