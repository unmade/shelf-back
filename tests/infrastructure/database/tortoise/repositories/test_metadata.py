from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.app.files.domain import ContentMetadata, File
from app.infrastructure.database.tortoise import models
from app.toolkit.metadata import Exif

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.files.domain import Namespace
    from app.infrastructure.database.tortoise.repositories import (
        ContentMetadataRepository,
    )

    from ..conftest import FileFactory

pytestmark = [pytest.mark.anyio, pytest.mark.database]


async def _get_by_file_id(file_id: UUID) -> models.FileMetadata:
    return await models.FileMetadata.get(file_id=file_id)


class TestGetByFileID:
    async def test(
        self,
        metadata_repo: ContentMetadataRepository,
        content_metadata: ContentMetadata,
    ):
        result = await metadata_repo.get_by_file_id(content_metadata.file_id)
        assert result == content_metadata

    async def test_when_file_does_not_exist(
        self,
        metadata_repo: ContentMetadataRepository,
    ):
        file_id = uuid.uuid4()
        with pytest.raises(ContentMetadata.NotFound):
            await metadata_repo.get_by_file_id(file_id)


class TestSave:
    async def test(self, metadata_repo: ContentMetadataRepository, file: File):
        exif = Exif(width=1280, height=800)
        given = ContentMetadata(file_id=file.id, data=exif)
        await metadata_repo.save(given)
        meta = await _get_by_file_id(file.id)
        assert meta.data == exif.model_dump(exclude_none=True)

    async def test_when_file_does_not_exist(
        self, metadata_repo: ContentMetadataRepository,
    ):
        exif = Exif(width=1280, height=800)
        metadata = ContentMetadata(file_id=uuid.uuid4(), data=exif)
        with pytest.raises(File.NotFound):
            await metadata_repo.save(metadata)


class TestSaveBatch:
    async def test(
        self,
        metadata_repo: ContentMetadataRepository,
        file_factory: FileFactory,
        namespace: Namespace,
    ):
        ns_path = str(namespace.path)
        files = [await file_factory(ns_path), await file_factory(ns_path)]
        given = [
            ContentMetadata(file_id=files[0].id, data=Exif(width=1280, height=800)),
            ContentMetadata(file_id=files[1].id, data=Exif(width=1440, height=900)),
        ]
        await metadata_repo.save_batch(given)
        meta = await _get_by_file_id(files[0].id)
        assert meta.data == given[0].data.model_dump(exclude_none=True)
        meta = await _get_by_file_id(files[1].id)
        assert meta.data == given[1].data.model_dump(exclude_none=True)

    async def test_when_file_does_not_exist(
        self,
        metadata_repo: ContentMetadataRepository,
    ):
        exif = Exif(width=1280, height=800)
        metadata = ContentMetadata(file_id=uuid.uuid4(), data=exif)
        with pytest.raises(File.NotFound):
            await metadata_repo.save_batch([metadata])
