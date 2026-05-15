from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.app.blobs.domain import Blob
from app.app.blobs.repositories.blob import BlobUpdate
from app.app.infrastructure.database import SENTINEL_ID
from app.infrastructure.database.tortoise import models
from app.toolkit import timezone

if TYPE_CHECKING:
    from uuid import UUID

    from app.infrastructure.database.tortoise.repositories import BlobRepository
    from tests.infrastructure.database.tortoise.conftest import BlobFactory

pytestmark = [pytest.mark.anyio, pytest.mark.database]


async def _blob_exists(blob_id: UUID) -> bool:
    return await models.Blob.filter(id=blob_id).exists()


async def _get_blob(blob_id: UUID) -> models.Blob:
    return await models.Blob.get(id=blob_id)


async def _get_blob_ids(blob_ids: list[UUID]) -> set[UUID]:
    blobs = await models.Blob.filter(id__in=blob_ids)
    return {blob.id for blob in blobs}


class TestDelete:
    async def test(self, blob_repo: BlobRepository, blob_factory: BlobFactory):
        # GIVEN
        blob = await blob_factory()
        # WHEN
        await blob_repo.delete(blob.id)
        # THEN
        assert not await _blob_exists(blob.id)


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
        remaining_ids = await _get_blob_ids([b.id for b in blobs])
        assert remaining_ids == {blobs[2].id}


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


class TestDeleteAllWithPrefix:
    async def test(self, blob_repo: BlobRepository, blob_factory: BlobFactory):
        # GIVEN
        blob_a = await blob_factory(storage_key="admin/files/a.txt")
        blob_b = await blob_factory(storage_key="admin/files/b.txt")
        kept = await blob_factory(storage_key="admin/other/c.txt")
        # WHEN
        await blob_repo.delete_all_with_prefix("admin/files/")
        # THEN
        remaining_ids = await _get_blob_ids([blob_a.id, blob_b.id, kept.id])
        assert remaining_ids == {kept.id}


class TestExistsWithStorageKey:
    async def test(self, blob_repo: BlobRepository, blob_factory: BlobFactory):
        blob = await blob_factory()
        assert await blob_repo.exists_with_storage_key(blob.storage_key)
        assert not await blob_repo.exists_with_storage_key(uuid.uuid4().hex)


class TestReplaceStorageKeyPrefix:
    async def test(self, blob_repo: BlobRepository, blob_factory: BlobFactory):
        # GIVEN
        blob_a = await blob_factory(storage_key="admin/a/f.txt")
        blob_b = await blob_factory(storage_key="admin/a/sub/g.txt")
        other = await blob_factory(storage_key="admin/other/h.txt")
        # WHEN
        await blob_repo.replace_storage_key_prefix(at="admin/a/", to="admin/z/")
        # THEN
        updated_a = await _get_blob(blob_a.id)
        updated_b = await _get_blob(blob_b.id)
        unchanged = await _get_blob(other.id)
        assert updated_a.storage_key == "admin/z/f.txt"
        assert updated_b.storage_key == "admin/z/sub/g.txt"
        assert unchanged.storage_key == "admin/other/h.txt"


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


class TestUpdate:
    async def test(self, blob_repo: BlobRepository, blob_factory: BlobFactory):
        # GIVEN
        blob = await blob_factory(storage_key="admin/a.txt")
        fields: BlobUpdate = {
            "storage_key": "admin/b.txt",
            "size": 42,
            "chash": uuid.uuid4().hex,
            "media_type": "image/png",
        }
        # WHEN
        await blob_repo.update(blob.id, fields)
        # THEN
        saved = await _get_blob(blob.id)
        assert saved.storage_key == fields["storage_key"]
        assert saved.size == fields["size"]
        assert saved.chash == fields["chash"]
        assert saved.media_type == fields["media_type"]
