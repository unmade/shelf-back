from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol

from app.app.blobs.domain import Blob
from app.app.infrastructure.database import SENTINEL_ID
from app.toolkit import chash as chash_mod
from app.toolkit import timezone

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence
    from uuid import UUID

    from app.app.blobs.domain import IBlobContent
    from app.app.blobs.repositories import IBlobRepository
    from app.app.infrastructure import IStorage

    class IServiceDatabase(Protocol):
        blob: IBlobRepository

__all__ = ["BlobService"]


class BlobService:
    __slots__ = ("db", "storage")

    def __init__(self, database: IServiceDatabase, storage: IStorage):
        self.db = database
        self.storage = storage

    async def create(
        self, storage_key: str, content: IBlobContent, media_type: str
    ) -> Blob:
        content_hash = await asyncio.to_thread(chash_mod.chash, content.file)
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

    async def delete(self, blob_id: UUID) -> None:
        blob = await self.db.blob.get_by_id(blob_id)
        await self.storage.delete(blob.storage_key)
        await self.db.blob.delete(blob_id)

    async def delete_batch(self, blob_ids: Sequence[UUID]) -> None:
        blobs = await self.db.blob.get_by_id_batch(blob_ids)
        keys = [blob.storage_key for blob in blobs]
        await self.storage.delete_batch(keys)
        await self.db.blob.delete_batch(blob_ids)

    def download(self, storage_key: str) -> AsyncIterator[bytes]:
        return self.storage.download(storage_key)

    async def get_by_id(self, blob_id: UUID) -> Blob:
        return await self.db.blob.get_by_id(blob_id)
