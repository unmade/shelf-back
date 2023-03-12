from __future__ import annotations

import asyncio
import contextlib
from typing import IO, TYPE_CHECKING, AsyncIterator, Protocol

from app import mediatypes, metadata
from app.domain.entities import ContentMetadata

if TYPE_CHECKING:
    from app.app.repositories.metadata import IContentMetadataRepository

    class IServiceDatabase(Protocol):
        metadata: IContentMetadataRepository


class MetadataService:
    """A service to track and retrieve file content metadata."""

    __slots__ = ["db"]

    def __init__(self, database: IServiceDatabase):
        self.db = database

    async def track(self, file_id: str, content: IO[bytes]) -> None:
        """
        Tracks file content metadata.

        Args:
            file_id (str): File ID to associate metadata with.
            data (Exif): Metadata.

        Raises:
            errors.FileNotFound: If a file with specified ID doesn't exist.
        """
        mediatype = mediatypes.guess("", content)
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
        mediatype = mediatypes.guess("", content)
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
