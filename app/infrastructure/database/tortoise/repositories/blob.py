from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise.exceptions import DoesNotExist

from app.app.blobs.domain import Blob
from app.app.blobs.repositories import IBlobRepository
from app.infrastructure.database.tortoise import models

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

__all__ = ["BlobRepository"]


def _from_db(obj: models.Blob) -> Blob:
    return Blob(
        id=obj.id,
        storage_key=obj.storage_key,
        size=obj.size,
        chash=obj.chash,
        media_type=obj.media_type,
        created_at=obj.created_at,
    )


class BlobRepository(IBlobRepository):
    async def delete(self, blob_id: UUID) -> None:
        await models.Blob.filter(id=blob_id).delete()

    async def delete_batch(self, blob_ids: Sequence[UUID]) -> None:
        await models.Blob.filter(id__in=list(blob_ids)).delete()

    async def get_by_id(self, blob_id: UUID) -> Blob:
        try:
            obj = await models.Blob.get(id=blob_id)
        except DoesNotExist as exc:
            raise Blob.NotFound() from exc
        return _from_db(obj)

    async def get_by_id_batch(self, blob_ids: Sequence[UUID]) -> list[Blob]:
        objs = await models.Blob.filter(id__in=list(blob_ids))
        return [_from_db(obj) for obj in objs]

    async def save(self, blob: Blob) -> Blob:
        obj = await models.Blob.create(
            storage_key=blob.storage_key,
            size=blob.size,
            chash=blob.chash,
            media_type=blob.media_type,
            created_at=blob.created_at,
        )
        return _from_db(obj)
