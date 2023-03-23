from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import orjson
import pytest

from app import errors
from app.domain.entities import ContentMetadata, Exif
from app.infrastructure.database.edgedb.db import db_context

if TYPE_CHECKING:
    from app.entities import File, Namespace
    from app.infrastructure.database.edgedb.repositories import (
        ContentMetadataRepository,
    )
    from app.typedefs import StrOrUUID

    from ..conftest import FileFactory

pytestmark = [pytest.mark.asyncio, pytest.mark.database]


async def _get_by_file_id(file_id: StrOrUUID):
    return await db_context.get().query_required_single("""
        SELECT FileMetadata { file: { id }, data }
        FILTER .file.id = <uuid>$file_id
        LIMIT 1
    """, file_id=file_id)


class TestGetByFileID:
    async def test(
        self,
        metadata_repo: ContentMetadataRepository,
        content_metadata: ContentMetadata,
    ):
        # WHEN
        result = await metadata_repo.get_by_file_id(content_metadata.file_id)
        # THEN
        assert result == content_metadata

    async def test_when_file_does_not_exist(
        self,
        metadata_repo: ContentMetadataRepository,
        content_metadata: ContentMetadata,
    ):
        file_id = str(uuid.uuid4())
        with pytest.raises(errors.FileMetadataNotFound):
            await metadata_repo.get_by_file_id(file_id)


class TestSave:
    async def test(self, metadata_repo: ContentMetadataRepository, file: File):
        # GIVEN
        exif = Exif(width=1280, height=800)
        given = ContentMetadata(file_id=file.id, data=exif)
        # WHEN
        await metadata_repo.save(given)
        # THEN
        meta = await _get_by_file_id(file.id)
        assert orjson.loads(meta.data) == exif.dict(exclude_none=True)

    async def test_when_file_does_not_exist(
        self, metadata_repo: ContentMetadataRepository,
    ):
        exif = Exif(width=1280, height=800)
        metadata = ContentMetadata(file_id=str(uuid.uuid4()), data=exif)
        with pytest.raises(errors.FileNotFound):
            await metadata_repo.save(metadata)


class TestSaveBatch:
    async def test(
        self,
        metadata_repo: ContentMetadataRepository,
        file_factory: FileFactory,
        namespace: Namespace,
    ):
        # GIVEN
        ns_path = str(namespace.path)
        files = [await file_factory(ns_path), await file_factory(ns_path)]
        given = [
            ContentMetadata(file_id=files[0].id, data=Exif(width=1280, height=800)),
            ContentMetadata(file_id=files[1].id, data=Exif(width=1440, height=900)),
        ]
        # WHEN
        await metadata_repo.save_batch(given)
        # THEN
        meta = await _get_by_file_id(files[0].id)
        assert orjson.loads(meta.data) == given[0].data.dict(exclude_none=True)
        meta = await _get_by_file_id(files[1].id)
        assert orjson.loads(meta.data) == given[1].data.dict(exclude_none=True)

    async def test_when_file_does_not_exist(
        self,
        metadata_repo: ContentMetadataRepository,
    ):
        exif = Exif(width=1280, height=800)
        metadata = ContentMetadata(file_id=str(uuid.uuid4()), data=exif)
        with pytest.raises(errors.FileNotFound):
            await metadata_repo.save_batch([metadata])
