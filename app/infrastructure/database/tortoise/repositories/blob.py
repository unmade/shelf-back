from __future__ import annotations

from typing import TYPE_CHECKING

from pypika_tortoise.terms import Function as PypikaFunction
from tortoise.exceptions import DoesNotExist
from tortoise.expressions import F, Function

from app.app.blobs.domain import Blob
from app.app.blobs.repositories import IBlobRepository
from app.app.blobs.repositories.blob import BlobUpdate
from app.infrastructure.database.tortoise import models

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

__all__ = ["BlobRepository"]


class _Replace(Function):
    class _PypikaReplace(PypikaFunction):
        def __init__(self, field: F, find: str, replace: str) -> None:
            super().__init__("REPLACE", field, find, replace)

    database_func = _PypikaReplace


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

    async def delete_all_with_prefix(self, prefix: str) -> None:
        await models.Blob.filter(storage_key__startswith=prefix).delete()

    async def delete_batch(self, blob_ids: Sequence[UUID]) -> None:
        await models.Blob.filter(id__in=list(blob_ids)).delete()

    async def exists_with_storage_key(self, storage_key: str) -> bool:
        return await models.Blob.filter(storage_key=storage_key).exists()

    async def get_by_id(self, blob_id: UUID) -> Blob:
        try:
            obj = await models.Blob.get(id=blob_id)
        except DoesNotExist as exc:
            raise Blob.NotFound() from exc
        return _from_db(obj)

    async def get_by_id_batch(self, blob_ids: Sequence[UUID]) -> list[Blob]:
        objs = await models.Blob.filter(id__in=list(blob_ids))
        return [_from_db(obj) for obj in objs]

    async def replace_storage_key_prefix(self, at: str, to: str) -> None:
        await models.Blob.filter(storage_key__startswith=at).update(
            storage_key=_Replace(F("storage_key"), at, to)
        )

    async def save(self, blob: Blob) -> Blob:
        obj = await models.Blob.create(
            storage_key=blob.storage_key,
            size=blob.size,
            chash=blob.chash,
            media_type=blob.media_type,
            created_at=blob.created_at,
        )
        return _from_db(obj)

    async def update(self, blob_id: UUID, fields: BlobUpdate) -> None:
        assert fields, "At least one field must be provided for update"
        await models.Blob.filter(id=blob_id).update(**fields)
