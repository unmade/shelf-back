from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from app import errors, tasks
from app.entities import RelocationPath

if TYPE_CHECKING:
    from app.entities import User


pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("celery_session_worker")]


def test_celery_works():
    task = tasks.ping.delay()
    assert task.get(timeout=1) == "pong"


async def test_move_batch(user: User, file_factory):
    await file_factory(user.id, path="folder/a")
    files = await asyncio.gather(*(file_factory(user.id) for _ in range(2)))
    relocations = [
        RelocationPath(from_path=files[0].path, to_path=f"folder/{files[0].path}"),
        RelocationPath(from_path=files[1].path, to_path=f"not_exists/{files[1].path}"),
    ]

    task = tasks.move_batch.delay(user.namespace, relocations)
    result = task.get(timeout=2)
    assert len(result) == 2

    assert result[0].file is not None
    assert result[0].file.path == relocations[0].to_path

    assert result[1].file is None
    assert result[1].err_code == errors.ErrorCode.missing_parent


async def test_move_to_trash_batch(user: User, file_factory):
    await file_factory(user.id, path="folder/a")
    files = await asyncio.gather(*(file_factory(user.id) for _ in range(2)))
    paths = [files[0].path, "file_not_exist.txt"]

    task = tasks.move_to_trash_batch.delay(user.namespace, paths)
    result = task.get(timeout=2)
    assert len(result) == 2

    assert result[0].file is not None
    assert result[0].file.path == f"Trash/{paths[0]}"

    assert result[1].file is None
    assert result[1].err_code == errors.ErrorCode.file_not_found
