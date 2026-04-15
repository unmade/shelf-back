from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.app.blobs.domain import Blob
from app.app.infrastructure.database import SENTINEL_ID
from app.toolkit import timezone

if TYPE_CHECKING:
    from app.infrastructure.database.tortoise.repositories import BlobRepository
    from tests.infrastructure.database.tortoise.conftest import BlobFactory

pytestmark = [pytest.mark.anyio, pytest.mark.database]


class TestDelete:
    async def test(self, blob_repo: BlobRepository, blob_factory: BlobFactory):
        # GIVEN
        blob = await blob_factory()
        # WHEN
        await blob_repo.delete(blob.id)
        # THEN
        with pytest.raises(Blob.NotFound):
            await blob_repo.get_by_id(blob.id)


class TestDeleteBatch:
    async def test(self, blob_repo: BlobRepository, blob_factory: BlobFactory):
        # GIVEN
        blobs = [
            await blob_factory(),
            await blob_factory(),
            await blob_factory(),
        ]
        ids = [b.id for b in blobs[:2]]
        # WHEN
        await blob_repo.delete_batch(ids)
        # THEN
        remaining = await blob_repo.get_by_id_batch([b.id for b in blobs])
        assert len(remaining) == 1
        assert remaining[0].id == blobs[2].id


class TestGetById:
    async def test(self, blob_repo: BlobRepository, blob_factory: BlobFactory):
        # GIVEN
        saved = await blob_factory()
        # WHEN
        result = await blob_repo.get_by_id(saved.id)
        # THEN
        assert result == saved

    async def test_when_not_found(self, blob_repo: BlobRepository):
        # GIVEN
        blob_id = uuid.uuid4()
        # WHEN / THEN
        with pytest.raises(Blob.NotFound):
            await blob_repo.get_by_id(blob_id)


class TestGetByIdBatch:
    async def test(self, blob_repo: BlobRepository, blob_factory: BlobFactory):
        # GIVEN
        blobs = [
            await blob_factory(),
            await blob_factory(),
            await blob_factory(),
        ]
        ids = [b.id for b in blobs[:2]]
        # WHEN
        result = await blob_repo.get_by_id_batch(ids)
        # THEN
        assert sorted(result, key=lambda b: b.storage_key) == sorted(
            blobs[:2], key=lambda b: b.storage_key
        )


class TestSave:
    async def test(self, blob_repo: BlobRepository):
        # GIVEN
        blob = Blob(
            id=SENTINEL_ID,
            storage_key=f"blobs/{uuid.uuid7().hex}",
            size=1024,
            chash=uuid.uuid4().hex,
            media_type="plain/text",
            created_at=timezone.now(),
        )
        # WHEN
        result = await blob_repo.save(blob)
        # THEN
        assert result.id != SENTINEL_ID
        assert result.storage_key == blob.storage_key
        assert result.size == blob.size
        assert result.chash == blob.chash
        assert result.media_type == blob.media_type
