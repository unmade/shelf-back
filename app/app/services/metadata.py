from __future__ import annotations

from typing import IO, TYPE_CHECKING, Protocol

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
            ContentMetadata(
                file_id=file_id,
                data=meta,
            )
        )
