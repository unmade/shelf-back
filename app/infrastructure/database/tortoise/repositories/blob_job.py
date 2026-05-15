from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import TypeAdapter

from app.app.blobs.domain import BlobJob, BlobJobPayload
from app.app.blobs.repositories import IBlobJobRepository
from app.infrastructure.database.tortoise import models

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

__all__ = ["BlobJobRepository"]

_payload_adapter: TypeAdapter[BlobJobPayload] = TypeAdapter(BlobJobPayload)


def _from_db(obj: models.BlobJob) -> BlobJob:
    payload = _payload_adapter.validate_python(obj.data)
    return BlobJob(
        id=obj.id,
        payload=payload,
        created_at=obj.created_at,
    )


class BlobJobRepository(IBlobJobRepository):
    async def delete_by_id_batch(self, ids: Sequence[UUID]) -> None:
        await models.BlobJob.filter(id__in=list(ids)).delete()

    async def get_by_id_batch(self, ids: Sequence[UUID]) -> list[BlobJob]:
        objs = await models.BlobJob.filter(id__in=list(ids))
        return [_from_db(obj) for obj in objs]

    async def save_batch(self, jobs: Sequence[BlobJob]) -> list[BlobJob]:
        db_objs = [
            models.BlobJob(
                type=job.payload.type,
                data=job.payload.model_dump(mode="json"),
                created_at=job.created_at,
            )
            for job in jobs
        ]
        await models.BlobJob.bulk_create(db_objs)
        return [_from_db(obj) for obj in db_objs]
