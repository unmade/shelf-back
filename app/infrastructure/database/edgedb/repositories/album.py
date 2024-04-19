from __future__ import annotations

from typing import TYPE_CHECKING

from app.app.photos.domain import Album
from app.app.photos.repositories import IAlbumRepository

if TYPE_CHECKING:

    from app.infrastructure.database.edgedb.typedefs import EdgeDBAnyConn, EdgeDBContext

__all__ = ["AlbumRepository"]


def _from_db(obj) -> Album:
    return Album(
        id=obj.id,
        owner_id=obj.owner.id,
        title=obj.title,
        created_at=obj.created_at,
        cover=Album.Cover(
            file_id=obj.cover.id,
        ),
    )


class AlbumRepository(IAlbumRepository):
    def __init__(self, db_context: EdgeDBContext):
        self.db_context = db_context

    @property
    def conn(self) -> EdgeDBAnyConn:
        return self.db_context.get()

    async def save(self, entity: Album) -> Album:
        query = """
            WITH
                owner := (SELECT User FILTER .id = <uuid>$owner_id),
            INSERT Album {
                title := <str>$title,
                owner := owner,
                created_at := <datetime>$created_at,
            }
        """

        obj = await self.conn.query_required_single(
            query,
            title=entity.title,
            owner_id=entity.owner_id,
            created_at=entity.created_at,
        )

        return entity.model_copy(update={"id": obj.id})
