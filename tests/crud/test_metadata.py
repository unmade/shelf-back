from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app import crud, errors
from app.entities import Exif, FileMetadata

if TYPE_CHECKING:
    from app.entities import Namespace
    from app.typedefs import DBTransaction
    from tests.factories import FileFactory, FileMetadataFactory


pytestmark = [pytest.mark.asyncio, pytest.mark.database]


async def test_get(
    tx: DBTransaction,
    namespace: Namespace,
    file_factory: FileFactory,
    file_metadata_factory: FileMetadataFactory,
):
    exif = Exif(width=1280, height=800)
    file = await file_factory(namespace.path)
    await file_metadata_factory(file.id, data=exif)
    meta = await crud.metadata.get(tx, file_id=file.id)
    assert meta == FileMetadata(file_id=file.id, data=exif)


async def test_get_but_file_does_not_exist(tx: DBTransaction):
    file_id = uuid.uuid4()
    with pytest.raises(errors.FileMetadataNotFound):
        await crud.metadata.get(tx, file_id=file_id)


async def test_get_but_file_metadata_does_not_exists(
    tx: DBTransaction,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path)
    with pytest.raises(errors.FileMetadataNotFound):
        await crud.metadata.get(tx, file_id=file.id)
