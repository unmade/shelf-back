from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.audit.domain import CurrentUserContext
from app.app.files.domain import File, Path
from app.toolkit import chash
from app.worker.jobs import files
from app.worker.jobs.files import ErrorCode, RelocationPath

if TYPE_CHECKING:
    from pytest import LogCaptureFixture

    from app.app.files.domain import AnyPath
    from app.worker.main import ARQContext

pytestmark = [pytest.mark.anyio]


def _make_file(ns_path: str, path: AnyPath):
    return File(
        id=uuid.uuid4(),
        ns_path=ns_path,
        name=Path(path).name,
        path=Path(path),
        chash=chash.EMPTY_CONTENT_HASH,
        size=10,
        mediatype="plain/text",
    )


def _make_context() -> CurrentUserContext:
    return CurrentUserContext(
        user=CurrentUserContext.User(
            id=uuid.uuid4(),
            username="admin",
        )
    )


class TestDeleteImmediatelyBatch:
    async def test(self, caplog: LogCaptureFixture, arq_context: ARQContext):
        # GIVEN
        ns_path = "admin"
        side_effect = [
            _make_file(ns_path, "Trash/a.txt"),
            File.NotFound,
            Exception,
            _make_file(ns_path, "Tras/f.txt"),
        ]
        usecases = cast(mock.MagicMock, arq_context["usecases"])
        usecases.namespace.delete_item.side_effect = side_effect
        paths = ["a.txt", "b.txt", "c.txt", "d.txt"]

        # WHEN
        results = await files.delete_immediately_batch(arq_context, ns_path, paths)

        # THEN
        assert len(results) == 4

        assert results[0].file is not None
        assert results[0].file.path == side_effect[0].path

        assert results[1].file is None
        assert results[1].err_code == ErrorCode.file_not_found

        assert results[2].file is None
        assert results[2].err_code == ErrorCode.internal

        assert results[3].file is not None
        assert results[3].file.path == side_effect[3].path

        assert usecases.namespace.delete_item.await_count == len(results)

        msg = "Unexpectedly failed to delete a file"
        log_record = ("app.worker.jobs.files", logging.ERROR, msg)
        assert caplog.record_tuples == [log_record]


class TestEmptyTrash:
    async def test(self, arq_context: ARQContext):
        # GIVEN
        ns_path = "admin"
        context = _make_context()
        usecases = cast(mock.MagicMock, arq_context["usecases"])
        # WHEN
        await files.empty_trash(arq_context, ns_path, context=context)
        # THEN
        usecases.namespace.empty_trash.assert_awaited_once_with(ns_path)

    async def test_when_failed_unexpectedly(
        self, caplog: LogCaptureFixture, arq_context: ARQContext
    ):
        # GIVEN
        ns_path = "admin"
        context = _make_context()
        usecases = cast(mock.MagicMock, arq_context["usecases"])
        usecases.namespace.empty_trash.side_effect = Exception
        # WHEN
        await files.empty_trash(arq_context, ns_path, context=context)
        # THEN
        usecases.namespace.empty_trash.assert_awaited_once_with(ns_path)
        msg = "Unexpectedly failed to empty trash folder"
        log_record = ("app.worker.jobs.files", logging.ERROR, msg)
        assert caplog.record_tuples == [log_record]


class TestMoveBatch:
    async def test(self, caplog: LogCaptureFixture, arq_context: ARQContext):
        # GIVEN
        ns_path = "admin"
        context = _make_context()
        usecases = cast(mock.MagicMock, arq_context["usecases"])
        usecases.namespace.move_item.side_effect = [
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

        # WHEN
        results = await files.move_batch(
            arq_context, ns_path, relocations, context=context
        )

        # THEN
        assert len(results) == 4

        assert results[0].file is not None
        assert results[0].file.path == relocations[0].to_path

        assert results[1].file is None
        assert results[1].err_code == ErrorCode.missing_parent

        assert results[2].file is None
        assert results[2].err_code == ErrorCode.internal

        assert results[3].file is not None
        assert results[3].file.path == relocations[3].to_path

        assert usecases.namespace.move_item.await_count == len(results)

        msg = "Unexpectedly failed to move a file"
        log_record = ("app.worker.jobs.files", logging.ERROR, msg)
        assert caplog.record_tuples == [log_record]


class TestMovetoTrashFile:
    async def test(self, caplog: LogCaptureFixture, arq_context: ARQContext):
        # GIVEN
        ns_path = "admin"
        context = _make_context()
        side_effect = [
            _make_file(ns_path, "Trash/a.txt"),
            File.NotFound,
            Exception,
            _make_file(ns_path, "Tras/f.txt"),
        ]
        usecases = cast(mock.MagicMock, arq_context["usecases"])
        usecases.namespace.move_item_to_trash.side_effect = side_effect

        paths = ["a.txt", "b.txt", "c.txt", "d.txt"]

        # WHEN
        results = await files.move_to_trash_batch(
            arq_context, ns_path, paths, context=context
        )

        # THEN
        assert len(results) == len(side_effect)

        assert results[0].file is not None
        assert results[0].file.path == side_effect[0].path

        assert results[1].file is None
        assert results[1].err_code == ErrorCode.file_not_found

        assert results[2].file is None
        assert results[2].err_code == ErrorCode.internal

        assert results[3].file is not None
        assert results[3].file.path == side_effect[3].path

        assert usecases.namespace.move_item_to_trash.await_count == len(results)

        msg = "Unexpectedly failed to move file to trash"
        log_record = ("app.worker.jobs.files", logging.ERROR, msg)
        assert caplog.record_tuples == [log_record]


class TestProcessFileContent:
    async def test(self, arq_context: ARQContext):
        # GIVEN
        file_id = uuid.uuid4()
        usecases = cast(mock.MagicMock, arq_context["usecases"])
        content_service = usecases.namespace.content
        # WHEN
        await files.process_file_content(arq_context, file_id)
        # THEN
        content_service.process.assert_awaited_once_with(file_id)
