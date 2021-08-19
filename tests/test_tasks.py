from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app import errors, tasks
from app.entities import RelocationPath

if TYPE_CHECKING:
    from pytest import LogCaptureFixture
    from app.entities import Namespace
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


async def test_move(namespace: Namespace, file_factory: FileFactory):
    file = await file_factory(namespace.path, path="folder/x.txt")
    relocation = RelocationPath(from_path=file.path, to_path="y.txt")

    task = tasks.move.delay(namespace, relocation)
    result = task.get(timeout=2)

    assert result.file is not None
    assert result.file.id == file.id
    assert result.file.path == "y.txt"

    assert result.err_code is None


async def test_move_but_move_fails_with_error(namespace: Namespace):
    relocation = RelocationPath(from_path="x.txt", to_path="y.txt")

    task = tasks.move.delay(namespace, relocation)
    result = task.get(timeout=2)

    assert result.file is None
    assert result.err_code == errors.ErrorCode.file_not_found


async def test_move_but_move_fails_with_exception(
    caplog: LogCaptureFixture,
    namespace: Namespace,
):
    relocation = RelocationPath(from_path="x.txt", to_path="y.txt")

    task = tasks.move.delay(namespace, relocation)
    with mock.patch("app.actions.move", side_effect=Exception) as move_mock:
        result = task.get(timeout=2)

    assert move_mock.call_count == 1

    assert result.file is None
    assert result.err_code == errors.ErrorCode.internal

    log_record = ("app.tasks", logging.ERROR, "Unexpectedly failed to move file")
    assert caplog.record_tuples == [log_record]


async def test_move_batch(namespace: Namespace, file_factory: FileFactory):
    await file_factory(namespace.path, path="folder/a")
    files = [await file_factory(namespace.path) for _ in range(2)]
    relocations = [
        RelocationPath(from_path=files[0].path, to_path=f"folder/{files[0].path}"),
        RelocationPath(from_path=files[1].path, to_path=f"not_exists/{files[1].path}"),
    ]

    task = tasks.move_batch.delay(namespace, relocations)
    result = task.get(timeout=2)
    assert len(result) == 2

    assert result[0].file is not None
    assert result[0].file.path == relocations[0].to_path

    assert result[1].file is None
    assert result[1].err_code == errors.ErrorCode.missing_parent


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
        result = task.get(timeout=2)

    assert move_mock.call_count == 2

    assert len(result) == 2

    assert result[0].file is None
    assert result[0].err_code == errors.ErrorCode.internal

    assert result[1].file is None
    assert result[1].err_code == errors.ErrorCode.internal

    log_record = ("app.tasks", logging.ERROR, "Unexpectedly failed to move file")
    assert caplog.record_tuples == [log_record, log_record]


async def test_move_to_trash_batch(namespace: Namespace, file_factory: FileFactory):
    files = [await file_factory(namespace.path) for _ in range(2)]
    paths = [files[0].path, "file_not_exist.txt"]

    task = tasks.move_to_trash_batch.delay(namespace, paths)
    result = task.get(timeout=2)

    assert len(result) == 2

    assert result[0].file is not None
    assert result[0].file.path == f"Trash/{paths[0]}"

    assert result[1].file is None
    assert result[1].err_code == errors.ErrorCode.file_not_found


async def test_move_to_trash_batch_but_move_fails_with_exception(
    caplog: LogCaptureFixture,
    namespace: Namespace,
    file_factory: FileFactory,
):
    files = [await file_factory(namespace.path) for _ in range(2)]
    paths = [files[0].path, "file_not_exist.txt"]

    task = tasks.move_to_trash_batch.delay(namespace, paths)
    with mock.patch("app.actions.move_to_trash", side_effect=Exception) as move_mock:
        result = task.get(timeout=2)

    assert move_mock.call_count == 2

    assert len(result) == 2

    assert result[0].file is None
    assert result[0].err_code == errors.ErrorCode.internal
    assert result[1].file is None
    assert result[1].err_code == errors.ErrorCode.internal

    log_record = "app.tasks", logging.ERROR, "Unexpectedly failed to move file to trash"
    assert caplog.record_tuples == [log_record, log_record]
