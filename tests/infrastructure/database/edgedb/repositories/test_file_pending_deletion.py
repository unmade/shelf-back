from __future__ import annotations

import operator
import uuid
from typing import TYPE_CHECKING

import pytest

from app.app.files.domain import FilePendingDeletion
from app.app.infrastructure.database import SENTINEL_ID
from app.infrastructure.database.edgedb.repositories.file_pending_deletion import (
    FilePendingDeletionRepository,
)
from app.toolkit.mediatypes import MediaType

if TYPE_CHECKING:
    from tests.infrastructure.database.edgedb.conftest import FilePendingDeletionFactory

pytestmark = [pytest.mark.anyio, pytest.mark.database]


class TestDeleteByIdBatch:
    async def test(
        self,
        file_pending_deletion_repo: FilePendingDeletionRepository,
        file_pending_deletion_factory: FilePendingDeletionFactory,
    ):
        # GIVEN
        items = [
            await file_pending_deletion_factory(),
            await file_pending_deletion_factory(),
            await file_pending_deletion_factory(),
        ]
        ids = [item.id for item in items[:2]]
        # WHEN
        result = await file_pending_deletion_repo.delete_by_id_batch(ids)
        # THEN
        assert sorted(result, key=operator.attrgetter("created_at")) == items[:2]


class TestGetByIdBatch:
    async def test(
        self,
        file_pending_deletion_repo: FilePendingDeletionRepository,
        file_pending_deletion_factory: FilePendingDeletionFactory,
    ):
        # GIVEN
        items = [
            await file_pending_deletion_factory(),
            await file_pending_deletion_factory(),
            await file_pending_deletion_factory(),
        ]
        ids = [item.id for item in items[:2]]
        # WHEN
        result = await file_pending_deletion_repo.get_by_id_batch(ids)
        # THEN
        assert sorted(result, key=operator.attrgetter("created_at")) == items[:2]


class TestSaveBatch:
    async def test(self, file_pending_deletion_repo: FilePendingDeletionRepository):
        # GIVEN
        entities = [
            FilePendingDeletion(
                id=SENTINEL_ID,
                ns_path="admin",
                path="f.txt",
                chash=uuid.uuid4().hex,
                mediatype=MediaType.PLAIN_TEXT,
            ),
            FilePendingDeletion(
                id=SENTINEL_ID,
                ns_path="admin",
                path="folder",
                chash=uuid.uuid4().hex,
                mediatype=MediaType.FOLDER,
            ),
        ]
        # WHEN
        result = await file_pending_deletion_repo.save_batch(entities)
        # THEN
        assert result[0].id != SENTINEL_ID
        assert result[1].id != SENTINEL_ID
        expected = [entity.model_dump(exclude={"id"}) for entity in entities]
        actual = [entity.model_dump(exclude={"id"}) for entity in result]
        assert actual == expected
