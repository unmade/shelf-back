from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise.exceptions import DoesNotExist, IntegrityError

from app.app.blobs.domain import Blob, BlobMetadata
from app.app.blobs.repositories import IBlobMetadataRepository
from app.infrastructure.database.tortoise import models

if TYPE_CHECKING:
    from uuid import UUID

__all__ = ["BlobMetadataRepository"]


def _from_db(obj: models.BlobMetadata) -> BlobMetadata:
    return BlobMetadata(
        blob_id=obj.blob_id,  # type: ignore[attr-defined]
        data=obj.data,
    )


class BlobMetadataRepository(IBlobMetadataRepository):
    async def get_by_blob_id(self, blob_id: UUID) -> BlobMetadata:
        try:
            obj = await models.BlobMetadata.get(blob_id=blob_id)
        except DoesNotExist as exc:
            raise BlobMetadata.NotFound() from exc
        return _from_db(obj)

    async def save(self, metadata: BlobMetadata) -> BlobMetadata:
        try:
            await models.BlobMetadata.create(
                blob_id=metadata.blob_id,
                data=metadata.data,
            )
        except IntegrityError as exc:
            raise Blob.NotFound() from exc
        return metadata
