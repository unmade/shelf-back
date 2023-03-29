from __future__ import annotations

import asyncio
import contextlib
from typing import IO, TYPE_CHECKING, AsyncIterator, Protocol

from app import metadata
from app.app.files.domain import ContentMetadata, mediatypes

if TYPE_CHECKING:
    from app.app.files.repositories.metadata import IContentMetadataRepository

    class IServiceDatabase(Protocol):
        metadata: IContentMetadataRepository


class MetadataService:
    """A service to track and retrieve file content metadata."""

    __slots__ = ["db"]

    def __init__(self, database: IServiceDatabase):
        self.db = database

    async def get_by_file_id(self, file_id: str) -> ContentMetadata:
        """
        Get metadata associated with a given File ID.

        Args:
            file_id (str): Target File ID.

        Raises:
            ContentMetadata.NotFound: If FileMetada for a given file ID does not exist.

        Returns:
            ContentMetadata: File content metadata.
        """
        return await self.db.metadata.get_by_file_id(file_id)

    async def track(self, file_id: str, content: IO[bytes]) -> None:
        """
        Tracks file content metadata.

        Args:
            file_id (str): File ID to associate metadata with.
            data (Exif): Metadata.

        Raises:
            File.NotFound: If a file with specified ID doesn't exist.
        """
        mediatype = mediatypes.guess(content)
        meta = metadata.load(content, mediatype=mediatype)
        if meta is None:
            return

        await self.db.metadata.save(
            ContentMetadata(file_id=file_id, data=meta)
        )

    @contextlib.asynccontextmanager
    async def track_batch(self) -> AsyncIterator[_Tracker]:
        tracker = _Tracker()
        try:
            yield tracker
        finally:
            await self.db.metadata.save_batch(tracker)


class _Tracker:
    def __init__(self):
        self._items = []

    async def add(self, file_id: str, content: IO[bytes]) -> None:
        loop = asyncio.get_running_loop()
        mediatype = mediatypes.guess(content)
        meta = await loop.run_in_executor(None, metadata.load, content, mediatype)
        if meta is None:
            return

        self._items.append(
            ContentMetadata(file_id=file_id, data=meta)
        )

    def __eq__(self, other) -> bool:
        if isinstance(other, _Tracker):
            return self._items == other._items
        return NotImplemented

    def __iter__(self):
        return iter(self._items)
