from __future__ import annotations

from typing import TYPE_CHECKING

from app.app.files.domain import FilePendingDeletion
from app.app.files.repositories import IFilePendingDeletionRepository
from app.infrastructure.database.tortoise import models

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

__all__ = ["FilePendingDeletionRepository"]


def _from_db(obj: models.FilePendingDeletion) -> FilePendingDeletion:
    return FilePendingDeletion(
        id=obj.id,
        ns_path=obj.ns_path,
        path=obj.path,
        chash=obj.chash,
        mediatype=obj.mediatype,
        created_at=obj.created_at,
    )


class FilePendingDeletionRepository(IFilePendingDeletionRepository):
    async def delete_by_id_batch(
        self, ids: Sequence[UUID]
    ) -> list[FilePendingDeletion]:
        objs = await models.FilePendingDeletion.filter(id__in=list(ids))
        await models.FilePendingDeletion.filter(id__in=list(ids)).delete()
        return [_from_db(obj) for obj in objs]

    async def get_by_id_batch(
        self, ids: Sequence[UUID]
    ) -> list[FilePendingDeletion]:
        objs = await models.FilePendingDeletion.filter(id__in=list(ids))
        return [_from_db(obj) for obj in objs]

    async def save_batch(
        self, entities: Sequence[FilePendingDeletion]
    ) -> list[FilePendingDeletion]:
        db_objs = [
            models.FilePendingDeletion(
                ns_path=entity.ns_path,
                path=entity.path,
                chash=entity.chash,
                mediatype=entity.mediatype,
                created_at=entity.created_at,
            )
            for entity in entities
        ]
        await models.FilePendingDeletion.bulk_create(db_objs)
        return [_from_db(obj) for obj in db_objs]
