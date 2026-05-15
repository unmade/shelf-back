from __future__ import annotations

import operator
import uuid
from typing import TYPE_CHECKING

import pytest

from app.app.blobs.domain import BlobJob
from app.app.blobs.domain.blob_job import BlobJobDeletePayload, BlobJobMovePayload
from app.app.infrastructure.database import SENTINEL_ID
from app.infrastructure.database.tortoise import models

if TYPE_CHECKING:
    from uuid import UUID

    from app.infrastructure.database.tortoise.repositories import BlobJobRepository

    from ..conftest import BlobJobFactory

pytestmark = [pytest.mark.anyio, pytest.mark.database]


async def _get_blob_job_ids(blob_job_ids: list[UUID]) -> set[UUID]:
    blob_jobs = await models.BlobJob.filter(id__in=blob_job_ids)
    return {blob_job.id for blob_job in blob_jobs}


class TestDeleteByIdBatch:
    async def test(
        self,
        blob_job_repo: BlobJobRepository,
        blob_job_factory: BlobJobFactory,
    ):
        # GIVEN
        items = [
            await blob_job_factory(),
            await blob_job_factory(),
            await blob_job_factory(),
        ]
        ids = [item.id for item in items[:2]]

        # WHEN
        await blob_job_repo.delete_by_id_batch(ids)

        # THEN
        remaining_ids = await _get_blob_job_ids([item.id for item in items])
        assert remaining_ids == {items[2].id}


class TestGetByIdBatch:
    async def test(
        self,
        blob_job_repo: BlobJobRepository,
        blob_job_factory: BlobJobFactory,
    ):
        # GIVEN
        items = [
            await blob_job_factory(),
            await blob_job_factory(),
            await blob_job_factory(),
        ]
        ids = [item.id for item in items[:2]]

        # WHEN
        result = await blob_job_repo.get_by_id_batch(ids)

        # THEN
        assert sorted(result, key=operator.attrgetter("created_at")) == items[:2]


class TestSaveBatch:
    async def test(self, blob_job_repo: BlobJobRepository):
        # GIVEN
        jobs = [
            BlobJob(
                id=SENTINEL_ID,
                payload=BlobJobDeletePayload(
                    blob_id=uuid.uuid7(),
                    storage_key="admin/f.txt",
                ),
            ),
            BlobJob(
                id=SENTINEL_ID,
                payload=BlobJobMovePayload(
                    blob_id=uuid.uuid7(),
                    at_storage_key="admin/a.jpg",
                    to_storage_key="admin/folder/a.jpg",
                ),
            ),
        ]

        # WHEN
        result = await blob_job_repo.save_batch(jobs)

        # THEN
        assert result[0].id != SENTINEL_ID
        assert result[1].id != SENTINEL_ID
        assert result[0].payload == jobs[0].payload
        assert result[1].payload == jobs[1].payload
