from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.app.infrastructure.database import SENTINEL_ID
from app.app.photos.domain import Album
from app.app.photos.repositories import IAlbumRepository

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    class IServiceDatabase(Protocol):
        album: IAlbumRepository


class AlbumService:
    __slots__ = ["db"]

    def __init__(self, database: IServiceDatabase):
        self.db = database

    async def create(self, title: str, owner_id: UUID, created_at: datetime) -> Album:
        """Creates a new album."""
        return await self.db.album.save(
            Album(
                id=SENTINEL_ID,
                title=title,
                owner_id=owner_id,
                created_at=created_at,
            )
        )
