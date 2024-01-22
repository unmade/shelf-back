from __future__ import annotations

from tempfile import SpooledTemporaryFile
from typing import IO, TYPE_CHECKING, Protocol

from app.app.files.services.dupefinder import dhash
from app.app.files.services.metadata import readers as metadata_readers
from app.config import ThumbnailSize, config
from app.toolkit import taskgroups
from app.toolkit.mediatypes import MediaType

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.files.domain import AnyPath, File
    from app.app.files.services import (
        DuplicateFinderService,
        MetadataService,
        ThumbnailService,
    )
    from app.app.files.services.file import FileCoreService
    from app.app.infrastructure import IIndexerClient
    from app.app.infrastructure.worker import IWorker

    class ITracker(Protocol):
        async def add(self, file_id: UUID, content: IO[bytes]) -> None:
            ...


class ContentService:
    __slots__ = (
        "dupefinder", "filecore", "indexer", "metadata", "thumbnailer", "worker"
    )

    def __init__(
        self,
        dupefinder: DuplicateFinderService,
        filecore: FileCoreService,
        indexer: IIndexerClient | None,
        metadata: MetadataService,
        thumbnailer: ThumbnailService,
        worker: IWorker,
    ):
        self.dupefinder = dupefinder
        self.filecore = filecore
        self.metadata = metadata
        self.indexer = indexer
        self.thumbnailer = thumbnailer
        self.worker = worker

    async def process(self, file_id: UUID) -> None:
        """
        Pre-generates thumbnails, calculates fingerprint and extract metadata from
        file content.
        """
        file, chunks = await self.filecore.download(file_id)
        with SpooledTemporaryFile() as content:
            async for chunk in chunks:
                content.write(chunk)

            await self.thumbnailer.generate_thumbnails(
                file_id,
                sizes=config.features.pre_generated_thumbnail_sizes,
            )
            if self.indexer is not None:
                size = ThumbnailSize.lg
                storage_path = self.thumbnailer.get_storage_path(file.chash, size)
                taskgroups.schedule(self.indexer.track(file.id, storage_path))

            await self.dupefinder.track(file.id, content)
            await self.metadata.track(file.id, content)

    async def process_async(self, file_id: UUID) -> None:
        """Schedules file content processing in a worker."""
        await self.worker.enqueue("process_file_content", file_id=file_id)

    async def reindex_contents(self, ns_path: AnyPath) -> None:
        """
        Restores additional information about files, such as fingerprint and content
        metadata.
        """
        def get_trackers(mediatype: str) -> list[ITracker]:
            if mediatype in types:
                return [dupefinder_tracker, metadata_tracker, chasher]
            return [chasher]

        types = tuple(dhash.SUPPORTED_TYPES | metadata_readers.SUPPORTED_TYPES)
        ns_path = str(ns_path)
        batch_size = 500
        batches = self.filecore.iter_files(
            ns_path, excluded_mediatypes=[MediaType.FOLDER], batch_size=batch_size
        )

        async for files in batches:
            async with (
                self.dupefinder.track_batch() as dupefinder_tracker,
                self.metadata.track_batch() as metadata_tracker,
                self.filecore.chash_batch() as chasher,
            ):
                await taskgroups.gather(*(
                    self._reindex_content(
                        file,
                        trackers=get_trackers(file.mediatype),
                    )
                    for file in files
                ))

    async def _reindex_content(self, file: File, trackers: list[ITracker]) -> None:
        _, chunks = await self.filecore.download(file.id)
        with SpooledTemporaryFile() as content:
            async for chunk in chunks:
                content.write(chunk)

            for tracker in trackers:
                await tracker.add(file.id, content)
