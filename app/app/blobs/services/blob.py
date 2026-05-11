from __future__ import annotations

import asyncio
import os.path
from typing import TYPE_CHECKING, Protocol

from app.app.blobs.domain import Blob, BlobJob
from app.app.blobs.domain.blob_job import (
    BlobJobDeletePayload,
    BlobJobDeletePrefixPayload,
    BlobJobMovePayload,
    BlobJobMovePrefixPayload,
)
from app.app.infrastructure.database import SENTINEL_ID
from app.app.infrastructure.storage import DownloadBatchItem
from app.toolkit import chash as chash_mod
from app.toolkit import mediatypes, timezone

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable, Sequence
    from uuid import UUID

    from app.app.blobs.domain import IBlobContent
    from app.app.blobs.repositories import IBlobJobRepository, IBlobRepository
    from app.app.infrastructure import IStorage, IWorker
    from app.app.infrastructure.database import IDatabase

    class IServiceDatabase(IDatabase, Protocol):
        blob: IBlobRepository
        blob_job: IBlobJobRepository

__all__ = ["BlobService"]


class BlobService:
    __slots__ = ("db", "storage", "worker")

    def __init__(
        self,
        database: IServiceDatabase,
        storage: IStorage,
        worker: IWorker,
    ):
        self.db = database
        self.storage = storage
        self.worker = worker

    async def create(self, storage_key: str, content: IBlobContent) -> Blob:
        media_type = mediatypes.guess(content.file, name=storage_key)
        content_hash = await asyncio.to_thread(chash_mod.chash, content.file)
        await self.storage.makedirs(os.path.dirname(storage_key))
        storage_file = await self.storage.save(storage_key, content)
        blob = Blob(
            id=SENTINEL_ID,
            storage_key=storage_key,
            size=storage_file.size,
            chash=content_hash,
            media_type=media_type,
            created_at=timezone.now(),
        )
        return await self.db.blob.save(blob)

    async def delete_all_with_prefix(self, prefix: str) -> None:
        jobs = await self.db.blob_job.save_batch([
            BlobJob(
                id=SENTINEL_ID,
                payload=BlobJobDeletePrefixPayload(storage_key_prefix=prefix),
            )
        ])
        await self.worker.enqueue("process_blob_jobs", ids=[job.id for job in jobs])

    async def delete_batch(self, blob_ids: Sequence[UUID]) -> None:
        if not blob_ids:
            return

        blobs = await self.db.blob.get_by_id_batch(blob_ids)
        if not blobs:
            return

        jobs = await self.db.blob_job.save_batch([
            BlobJob(
                id=SENTINEL_ID,
                payload=BlobJobDeletePayload(
                    blob_id=blob.id,
                    storage_key=blob.storage_key,
                ),
            )
            for blob in blobs
        ])
        await self.worker.enqueue("process_blob_jobs", ids=[job.id for job in jobs])

    async def move(self, blob_id: UUID, storage_key: str) -> None:
        blob = await self.db.blob.get_by_id(blob_id)
        if blob.storage_key == storage_key:
            return

        if await self.db.blob.exists_with_storage_key(storage_key):
            raise Blob.AlreadyExists()

        jobs = await self.db.blob_job.save_batch([
            BlobJob(
                id=SENTINEL_ID,
                payload=BlobJobMovePayload(
                    blob_id=blob_id,
                    at_storage_key=blob.storage_key,
                    to_storage_key=storage_key,
                ),
            )
        ])
        await self.worker.enqueue("process_blob_jobs", ids=[job.id for job in jobs])

    async def move_with_prefix(self, prefix: str, to_prefix: str) -> None:
        jobs = await self.db.blob_job.save_batch([
            BlobJob(
                id=SENTINEL_ID,
                payload=BlobJobMovePrefixPayload(
                    at_storage_key_prefix=prefix,
                    to_storage_key_prefix=to_prefix,
                ),
            )
        ])
        await self.worker.enqueue("process_blob_jobs", ids=[job.id for job in jobs])

    def download(self, storage_key: str) -> AsyncIterator[bytes]:
        return self.storage.download(storage_key)

    def download_batch(self, items: Iterable[DownloadBatchItem]) -> Iterable[bytes]:
        return self.storage.download_batch(items)

    def download_with_prefix(self, prefix: str) -> Iterable[bytes]:
        return self.storage.downloaddir(prefix)

    async def get_by_id(self, blob_id: UUID) -> Blob:
        return await self.db.blob.get_by_id(blob_id)

    async def get_by_id_batch(self, blob_ids: Sequence[UUID]) -> list[Blob]:
        return await self.db.blob.get_by_id_batch(blob_ids)

    async def process_blob_jobs(self, ids: Sequence[UUID]) -> None:
        jobs = await self.db.blob_job.get_by_id_batch(ids)
        if not jobs:
            return

        await self._process_delete_jobs(jobs)
        await self._process_delete_prefix_jobs(jobs)
        await self._process_move_jobs(jobs)
        await self._process_move_prefix_jobs(jobs)

    async def _process_delete_jobs(self, jobs: list[BlobJob]) -> None:
        job_ids, blob_ids, storage_keys = [], [], []
        for job in jobs:
            if isinstance(job.payload, BlobJobDeletePayload):
                job_ids.append(job.id)
                blob_ids.append(job.payload.blob_id)
                storage_keys.append(job.payload.storage_key)

        if not job_ids:
            return

        await self.storage.delete_batch(storage_keys)
        async with self.db.atomic():
            await self.db.blob.delete_batch(blob_ids)
            await self.db.blob_job.delete_by_id_batch(job_ids)

    async def _process_delete_prefix_jobs(self, jobs: list[BlobJob]) -> None:
        for job in jobs:
            if isinstance(job.payload, BlobJobDeletePrefixPayload):
                prefix = job.payload.storage_key_prefix
                await self.storage.deletedir(prefix)
                async with self.db.atomic():
                    await self.db.blob.delete_all_with_prefix(prefix)
                    await self.db.blob_job.delete_by_id_batch([job.id])

    async def _process_move_jobs(self, jobs: list[BlobJob]) -> None:
        for job in jobs:
            if isinstance(job.payload, BlobJobMovePayload):
                payload = job.payload
                await self.storage.move(
                    at=payload.at_storage_key,
                    to=payload.to_storage_key,
                )
                async with self.db.atomic():
                    await self.db.blob.update(
                        payload.blob_id,
                        fields={"storage_key": payload.to_storage_key},
                    )
                    await self.db.blob_job.delete_by_id_batch([job.id])

    async def _process_move_prefix_jobs(self, jobs: list[BlobJob]) -> None:
        for job in jobs:
            if isinstance(job.payload, BlobJobMovePrefixPayload):
                payload = job.payload
                await self.storage.movedir(
                    at=payload.at_storage_key_prefix,
                    to=payload.to_storage_key_prefix,
                )
                async with self.db.atomic():
                    await self.db.blob.replace_storage_key_prefix(
                        at=payload.at_storage_key_prefix,
                        to=payload.to_storage_key_prefix,
                    )
                    await self.db.blob_job.delete_by_id_batch([job.id])
