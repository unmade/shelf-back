from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import orjson
import pytest

from app import errors
from app.domain.entities import ContentMetadata, Exif
from app.infrastructure.database.edgedb.db import db_context

if TYPE_CHECKING:
    from app.entities import Namespace
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


class TestSaveBatch:
    async def test(
        self,
        metadata_repo: ContentMetadataRepository,
        file_factory: FileFactory,
        namespace: Namespace,
    ):
        # GIVEN
        exif = Exif(width=1280, height=800)
        file = await file_factory(str(namespace.path))
        given = ContentMetadata(file_id=file.id, data=exif)
        # WHEN
        await metadata_repo.save(given)
        # THEN
        meta = await _get_by_file_id(file.id)
        assert str(meta.file.id) == file.id
        assert orjson.loads(meta.data) == {"type": "exif", "width": 1280, "height": 800}

    async def test_when_file_does_not_exist(
        self, metadata_repo: ContentMetadataRepository,
    ):
        exif = Exif(width=1280, height=800)
        metadata = ContentMetadata(file_id=str(uuid.uuid4()), data=exif)
        with pytest.raises(errors.FileNotFound):
            await metadata_repo.save(metadata)
