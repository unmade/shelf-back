from __future__ import annotations

from tempfile import SpooledTemporaryFile
from typing import TYPE_CHECKING

from app.config import config

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.blobs.services.blob import BlobService
    from app.app.blobs.services.metadata import BlobMetadataService
    from app.app.blobs.services.thumbnailer import BlobThumbnailService
    from app.app.infrastructure.worker import IWorker

__all__ = ["BlobContentProcessor"]


class BlobContentProcessor:
    __slots__ = ("blob_service", "metadata_service", "thumbnail_service", "worker")

    def __init__(
        self,
        blob_service: BlobService,
        metadata_service: BlobMetadataService,
        thumbnail_service: BlobThumbnailService,
        worker: IWorker,
    ):
        self.blob_service = blob_service
        self.metadata_service = metadata_service
        self.thumbnail_service = thumbnail_service
        self.worker = worker

    async def process(self, blob_id: UUID) -> None:
        """Downloads blob content, generates thumbnails, and extracts metadata."""
        blob = await self.blob_service.get_by_id(blob_id)
        chunks = self.blob_service.download(blob.storage_key)
        with SpooledTemporaryFile() as content:
            async for chunk in chunks:
                content.write(chunk)

            await self.thumbnail_service.generate(
                blob.chash,
                content,
                sizes=config.features.pre_generated_thumbnail_sizes,
            )
            content.seek(0)
            await self.metadata_service.track(blob.id, content)

    async def process_async(self, blob_id: UUID) -> None:
        """Schedules blob content processing in a worker."""
        await self.worker.enqueue("process_blob_content", blob_id=blob_id)
