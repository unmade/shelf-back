from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.app.blobs.domain import Blob, BlobMetadata
from app.app.blobs.domain.metadata import Exif
from app.infrastructure.database.tortoise import models

if TYPE_CHECKING:
    from uuid import UUID

    from app.infrastructure.database.tortoise.repositories import (
        BlobMetadataRepository,
    )

    from ..conftest import BlobFactory, BlobMetadataFactory

pytestmark = [pytest.mark.anyio, pytest.mark.database]


async def _get_by_blob_id(blob_id: UUID) -> models.BlobMetadata:
    return await models.BlobMetadata.get(blob_id=blob_id)


class TestGetByBlobId:
    async def test(
        self,
        blob_metadata_repo: BlobMetadataRepository,
        blob_factory: BlobFactory,
        blob_metadata_factory: BlobMetadataFactory
    ):
        # GIVEN
        blob = await blob_factory()
        metadata = await blob_metadata_factory(blob_id=blob.id, data=Exif(width=1280))
        # WHEN
        result = await blob_metadata_repo.get_by_blob_id(blob.id)
        # THEN
        assert result == metadata

    async def test_when_not_found(
        self, blob_metadata_repo: BlobMetadataRepository
    ):
        # GIVEN
        blob_id = uuid.uuid4()
        # WHEN / THEN
        with pytest.raises(BlobMetadata.NotFound):
            await blob_metadata_repo.get_by_blob_id(blob_id)


class TestSave:
    async def test(
        self,
        blob_metadata_repo: BlobMetadataRepository,
        blob_factory: BlobFactory,
    ):
        # GIVEN
        blob = await blob_factory()
        exif = Exif(width=1280, height=800)
        metadata = BlobMetadata(blob_id=blob.id, data=exif)
        # WHEN
        result = await blob_metadata_repo.save(metadata)
        # THEN
        assert result.blob_id == blob.id
        assert result.data == exif
        obj = await _get_by_blob_id(blob.id)
        assert obj.data == exif.model_dump()

    async def test_when_blob_does_not_exist(
        self, blob_metadata_repo: BlobMetadataRepository
    ):
        # GIVEN
        metadata = BlobMetadata(
            blob_id=uuid.uuid4(), data=Exif(width=1280, height=800)
        )
        # WHEN / THEN
        with pytest.raises(Blob.NotFound):
            await blob_metadata_repo.save(metadata)
