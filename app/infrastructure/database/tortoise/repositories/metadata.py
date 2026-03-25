from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise.exceptions import DoesNotExist, IntegrityError

from app.app.files.domain import ContentMetadata, File
from app.app.files.repositories import IContentMetadataRepository
from app.infrastructure.database.tortoise import models

if TYPE_CHECKING:
    from collections.abc import Iterable
    from uuid import UUID

__all__ = ["ContentMetadataRepository"]


def _from_db(obj: models.FileMetadata) -> ContentMetadata:
    return ContentMetadata(
        file_id=obj.file_id,  # type: ignore[attr-defined]
        data=obj.data,
    )


class ContentMetadataRepository(IContentMetadataRepository):
    async def get_by_file_id(self, file_id: UUID) -> ContentMetadata:
        try:
            obj = await models.FileMetadata.get(file_id=file_id)
        except DoesNotExist as exc:
            raise ContentMetadata.NotFound() from exc
        return _from_db(obj)

    async def save(self, metadata: ContentMetadata) -> ContentMetadata:
        data = metadata.data.model_dump(exclude_none=True)
        try:
            await models.FileMetadata.create(
                file_id=metadata.file_id,
                data=data,
            )
        except IntegrityError as exc:
            raise File.NotFound() from exc
        return metadata

    async def save_batch(self, metadatas: Iterable[ContentMetadata]) -> None:
        objs = [
            models.FileMetadata(
                file_id=item.file_id,
                data=item.data.model_dump(exclude_none=True),
            )
            for item in metadatas
        ]

        try:
            await models.FileMetadata.bulk_create(objs, ignore_conflicts=True)
        except IntegrityError as exc:
            raise File.NotFound() from exc
