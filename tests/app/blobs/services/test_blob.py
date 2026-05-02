from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.blobs.domain import Blob, BlobJob
from app.app.blobs.domain.blob_job import (
    BlobJobDeletePayload,
    BlobJobDeletePrefixPayload,
    BlobJobMovePayload,
    BlobJobMovePrefixPayload,
)
from app.app.infrastructure.database import SENTINEL_ID
from app.app.infrastructure.storage import DownloadBatchItem

if TYPE_CHECKING:
    from app.app.blobs.domain import IBlobContent
    from app.app.blobs.services import BlobService
    from tests.fixtures.app.files import ContentFactory

    from .conftest import BlobFactory

pytestmark = [pytest.mark.anyio, pytest.mark.database]


class TestCreate:
    async def test(self, blob_service: BlobService, content: IBlobContent):
        # GIVEN
        storage_key = "blobs/abc123"
        media_type = "image/jpeg"

        # WHEN
        blob = await blob_service.create(storage_key, content, media_type)

        # THEN
        assert blob.storage_key == storage_key
        assert blob.size == content.size
        assert blob.media_type == media_type
        assert await blob_service.storage.exists(storage_key)
        assert await blob_service.db.blob.get_by_id(blob.id) == blob


class TestDeleteAllWithPrefix:
    async def test(self, blob_service: BlobService):
        # GIVEN
        prefix = "admin/folder/"
        worker = cast(mock.AsyncMock, blob_service.worker)

        # WHEN
        await blob_service.delete_all_with_prefix(prefix)

        # THEN
        worker.enqueue.assert_awaited_once_with("process_blob_jobs", ids=mock.ANY)
        job_ids = worker.enqueue.await_args.kwargs["ids"]
        jobs = await blob_service.db.blob_job.get_by_id_batch(job_ids)
        assert len(jobs) == 1
        assert isinstance(jobs[0].payload, BlobJobDeletePrefixPayload)
        assert jobs[0].payload.storage_key_prefix == prefix


class TestDeleteBatch:
    async def test(
        self,
        blob_service: BlobService,
        blob_factory: BlobFactory,
        content_factory: ContentFactory,
    ):
        # GIVEN
        blob_a = await blob_factory("blobs/a.txt", content_factory())
        blob_b = await blob_factory("blobs/b.txt", content_factory())
        worker = cast(mock.AsyncMock, blob_service.worker)

        # WHEN
        await blob_service.delete_batch([blob_a.id, blob_b.id])

        # THEN
        worker.enqueue.assert_awaited_once_with("process_blob_jobs", ids=mock.ANY)
        job_ids = worker.enqueue.await_args.kwargs["ids"]
        jobs = await blob_service.db.blob_job.get_by_id_batch(job_ids)
        assert len(jobs) == 2
        payloads = [job.payload for job in jobs]
        assert all(isinstance(payload, BlobJobDeletePayload) for payload in payloads)
        delete_payloads = cast(list[BlobJobDeletePayload], payloads)
        assert {p.blob_id for p in delete_payloads} == {blob_a.id, blob_b.id}

    async def test_when_no_blobs_in_db(self, blob_service: BlobService):
        # GIVEN
        blob_ids = [uuid.uuid7()]
        worker = cast(mock.AsyncMock, blob_service.worker)
        # WHEN
        await blob_service.delete_batch(blob_ids)
        # THEN
        worker.enqueue.assert_not_awaited()

    async def test_when_empty_ids(self, blob_service: BlobService):
        # GIVEN
        worker = cast(mock.AsyncMock, blob_service.worker)
        # WHEN
        await blob_service.delete_batch([])
        # THEN
        worker.enqueue.assert_not_awaited()


class TestDownload:
    async def test(
        self,
        blob_service: BlobService,
        blob_factory: BlobFactory,
        content: IBlobContent,
    ):
        # GIVEN
        storage_key = "blobs/file.txt"
        await blob_factory(storage_key, content)
        # WHEN
        result = blob_service.download(storage_key)
        # THEN
        downloaded = b"".join([chunk async for chunk in result])
        assert len(downloaded) == content.size


class TestDownloadBatch:
    async def test(
        self,
        blob_service: BlobService,
        blob_factory: BlobFactory,
        content: IBlobContent,
    ):
        # GIVEN
        storage_key = "blobs/batch/file.txt"
        await blob_factory(storage_key, content)
        items = [
            DownloadBatchItem(key=storage_key, is_dir=False, archive_path="file.txt")
        ]
        # WHEN
        result = blob_service.download_batch(items)
        # THEN
        archive_bytes = b"".join(result)
        assert len(archive_bytes) > 0


class TestDownloadWithPrefix:
    async def test(
        self,
        blob_service: BlobService,
        blob_factory: BlobFactory,
        content: IBlobContent,
    ):
        # GIVEN
        prefix = "blobs/folder"
        await blob_factory(f"{prefix}/file.txt", content)
        # WHEN
        result = blob_service.download_with_prefix(prefix)
        # THEN
        archive_bytes = b"".join(result)
        assert len(archive_bytes) > 0


class TestGetById:
    async def test(
        self,
        blob_service: BlobService,
        blob_factory: BlobFactory,
        content: IBlobContent,
    ):
        blob = await blob_factory("blobs/file.txt", content)
        result = await blob_service.get_by_id(blob.id)
        assert result == blob


class TestGetByIdBatch:
    async def test(
        self,
        blob_service: BlobService,
        blob_factory: BlobFactory,
        content_factory: ContentFactory,
    ):
        # GIVEN
        blob_a = await blob_factory("blobs/a.txt", content_factory())
        blob_b = await blob_factory("blobs/b.txt", content_factory())
        # WHEN
        result = await blob_service.get_by_id_batch([blob_a.id, blob_b.id])
        # THEN
        assert sorted(result, key=lambda b: b.storage_key) == [blob_a, blob_b]


class TestMove:
    async def test(
        self,
        blob_service: BlobService,
        blob_factory: BlobFactory,
        content: IBlobContent,
    ):
        # GIVEN
        blob = await blob_factory("admin/f.txt", content)
        to_storage_key = "admin/.f.txt"
        worker = cast(mock.AsyncMock, blob_service.worker)
        # WHEN
        await blob_service.move(blob.id, to_storage_key)
        # THEN
        worker.enqueue.assert_awaited_once_with("process_blob_jobs", ids=mock.ANY)
        job_ids = worker.enqueue.await_args.kwargs["ids"]
        jobs = await blob_service.db.blob_job.get_by_id_batch(job_ids)
        assert len(jobs) == 1
        assert isinstance(jobs[0].payload, BlobJobMovePayload)
        payload = jobs[0].payload
        assert payload.blob_id == blob.id
        assert payload.at_storage_key == blob.storage_key
        assert payload.to_storage_key == to_storage_key

    async def test_when_same_storage_key(
        self,
        blob_service: BlobService,
        blob_factory: BlobFactory,
        content: IBlobContent,
    ):
        # GIVEN
        blob = await blob_factory("admin/f.txt", content)
        worker = cast(mock.AsyncMock, blob_service.worker)
        # WHEN
        await blob_service.move(blob.id, blob.storage_key)
        # THEN
        worker.enqueue.assert_not_awaited()

    async def test_when_destination_storage_key_exists(
        self,
        blob_service: BlobService,
        blob_factory: BlobFactory,
        content_factory: ContentFactory,
    ):
        # GIVEN
        blob_a = await blob_factory("admin/a.txt", content_factory())
        await blob_factory("admin/b.txt", content_factory())
        # WHEN / THEN
        with pytest.raises(Blob.AlreadyExists):
            await blob_service.move(blob_a.id, "admin/b.txt")


class TestMoveWithPrefix:
    async def test(self, blob_service: BlobService):
        # GIVEN
        prefix = "admin/a/"
        to_prefix = "admin/z/"
        worker = cast(mock.AsyncMock, blob_service.worker)
        # WHEN
        await blob_service.move_with_prefix(prefix, to_prefix)
        # THEN
        worker.enqueue.assert_awaited_once_with("process_blob_jobs", ids=mock.ANY)
        job_ids = worker.enqueue.await_args.kwargs["ids"]
        jobs = await blob_service.db.blob_job.get_by_id_batch(job_ids)
        assert len(jobs) == 1
        assert isinstance(jobs[0].payload, BlobJobMovePrefixPayload)
        assert jobs[0].payload.at_storage_key_prefix == prefix
        assert jobs[0].payload.to_storage_key_prefix == to_prefix


class TestProcessBlobJobs:
    async def test_delete_jobs(
        self,
        blob_service: BlobService,
        blob_factory: BlobFactory,
        content_factory: ContentFactory,
    ):
        # GIVEN
        blob_a = await blob_factory("blobs/a.txt", content_factory())
        blob_b = await blob_factory("blobs/b.txt", content_factory())
        jobs = await blob_service.db.blob_job.save_batch([
            BlobJob(
                id=SENTINEL_ID,
                payload=BlobJobDeletePayload(
                    blob_id=blob_a.id,
                    storage_key=blob_a.storage_key,
                ),
            ),
            BlobJob(
                id=SENTINEL_ID,
                payload=BlobJobDeletePayload(
                    blob_id=blob_b.id,
                    storage_key=blob_b.storage_key,
                ),
            ),
        ])
        job_ids = [j.id for j in jobs]

        # WHEN
        await blob_service.process_blob_jobs(job_ids)

        # THEN
        assert not await blob_service.storage.exists(blob_a.storage_key)
        assert not await blob_service.storage.exists(blob_b.storage_key)
        assert await blob_service.db.blob.get_by_id_batch([blob_a.id, blob_b.id]) == []
        assert await blob_service.db.blob_job.get_by_id_batch(job_ids) == []

    async def test_delete_prefix_job(
        self,
        blob_service: BlobService,
        blob_factory: BlobFactory,
        content_factory: ContentFactory,
    ):
        # GIVEN
        blob_a = await blob_factory("admin/folder/a.txt", content_factory())
        blob_b = await blob_factory("admin/folder/b.txt", content_factory())
        jobs = await blob_service.db.blob_job.save_batch([
            BlobJob(
                id=SENTINEL_ID,
                payload=BlobJobDeletePrefixPayload(storage_key_prefix="admin/folder/"),
            )
        ])
        job_ids = [j.id for j in jobs]

        # WHEN
        await blob_service.process_blob_jobs(job_ids)

        # THEN
        assert not await blob_service.storage.exists(blob_a.storage_key)
        assert not await blob_service.storage.exists(blob_b.storage_key)
        assert await blob_service.db.blob.get_by_id_batch([blob_a.id, blob_b.id]) == []
        assert await blob_service.db.blob_job.get_by_id_batch(job_ids) == []

    async def test_move_job(
        self,
        blob_service: BlobService,
        blob_factory: BlobFactory,
        content: IBlobContent,
    ):
        # GIVEN
        blob = await blob_factory("admin/f.txt", content)
        jobs = await blob_service.db.blob_job.save_batch([
            BlobJob(
                id=SENTINEL_ID,
                payload=BlobJobMovePayload(
                    blob_id=blob.id,
                    at_storage_key=blob.storage_key,
                    to_storage_key="admin/g.txt",
                ),
            )
        ])
        job_ids = [j.id for j in jobs]

        # WHEN
        await blob_service.process_blob_jobs(job_ids)

        # THEN
        assert not await blob_service.storage.exists("admin/f.txt")
        assert await blob_service.storage.exists("admin/g.txt")
        updated_blob = await blob_service.db.blob.get_by_id(blob.id)
        assert updated_blob.storage_key == "admin/g.txt"
        assert await blob_service.db.blob_job.get_by_id_batch(job_ids) == []

    async def test_move_prefix_job(
        self,
        blob_service: BlobService,
        blob_factory: BlobFactory,
        content: IBlobContent,
    ):
        # GIVEN
        blob = await blob_factory("admin/a/f.txt", content)
        jobs = await blob_service.db.blob_job.save_batch([
            BlobJob(
                id=SENTINEL_ID,
                payload=BlobJobMovePrefixPayload(
                    at_storage_key_prefix="admin/a/",
                    to_storage_key_prefix="admin/z/",
                ),
            )
        ])
        job_ids = [j.id for j in jobs]

        # WHEN
        await blob_service.process_blob_jobs(job_ids)

        # THEN
        assert not await blob_service.storage.exists("admin/a/f.txt")
        assert await blob_service.storage.exists("admin/z/f.txt")
        updated_blob = await blob_service.db.blob.get_by_id(blob.id)
        assert updated_blob.storage_key == "admin/z/f.txt"
        assert await blob_service.db.blob_job.get_by_id_batch(job_ids) == []

    async def test_when_no_jobs_found(self, blob_service: BlobService):
        # GIVEN
        ids = [uuid.uuid7()]
        # WHEN
        await blob_service.process_blob_jobs(ids)
        # THEN - no exception raised
