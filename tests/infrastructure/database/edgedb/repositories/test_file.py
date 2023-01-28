from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.domain.entities import Namespace

if TYPE_CHECKING:

    from app.domain.entities import File
    from app.infrastructure.database.edgedb.repositories import FileRepository


pytestmark = [pytest.mark.asyncio]


class TestExistsWithID:
    async def test_when_exists(
        self, namespace: Namespace, file: File, file_repo: FileRepository
    ):
        exists = await file_repo.exists_with_id(namespace.path, file.id)
        assert exists is True

    async def test_when_does_not_exist(
        self, namespace: Namespace, file_repo: FileRepository
    ):
        file_id = uuid.uuid4()
        exists = await file_repo.exists_with_id(namespace.path, file_id)
        assert exists is False
