from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, AsyncIterator, Protocol
from uuid import UUID

from app.app.files.domain import ContentMetadata

from . import readers

if TYPE_CHECKING:
    from app.app.files.domain import IFileContent
    from app.app.files.repositories.metadata import IContentMetadataRepository

    class IServiceDatabase(Protocol):
        metadata: IContentMetadataRepository


class MetadataService:
    """A service to track and retrieve file content metadata."""

    __slots__ = ["db"]

    def __init__(self, database: IServiceDatabase):
        self.db = database

    async def get_by_file_id(self, file_id: UUID) -> ContentMetadata:
        """
        Get metadata associated with a given File ID.

        Raises:
            ContentMetadata.NotFound: If FileMetada for a given file ID does not exist.
        """
        return await self.db.metadata.get_by_file_id(file_id)

    async def track(self, file_id: UUID, content: IFileContent) -> None:
        """
        Tracks file content metadata.

        Raises:
            File.NotFound: If a file with specified ID doesn't exist.
        """
        data = await readers.load(content.file)
        if data is None:
            return

        await self.db.metadata.save(
            ContentMetadata(file_id=file_id, data=data)
        )

    @contextlib.asynccontextmanager
    async def track_batch(self) -> AsyncIterator[_Tracker]:
        tracker = _Tracker()
        try:
            yield tracker
        finally:
            await self.db.metadata.save_batch(tracker.items)


class _Tracker:
    __slots__ = ["_items"]

    def __init__(self):
        self._items: list[ContentMetadata] = []

    @property
    def items(self) -> list[ContentMetadata]:
        return self._items

    async def add(self, file_id: UUID, content: IFileContent) -> None:
        data = await readers.load(content.file)
        if data is None:
            return

        self._items.append(
            ContentMetadata(file_id=file_id, data=data)
        )
