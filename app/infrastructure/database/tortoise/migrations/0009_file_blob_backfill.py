from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from tortoise import migrations
from tortoise.migrations import operations as ops

from app.toolkit.mediatypes import MediaType

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.infrastructure.database.tortoise.models import (
        Blob,
        BlobMetadata,
        File,
        FileMetadata,
    )


def _storage_key(ns_path: str, path: str) -> str:
    return f"{ns_path}/{path}"


async def backfill_files_to_blobs(apps, _schema_editor) -> None:
    BlobModel = apps.get_model("models.Blob")
    BlobMetadataModel = apps.get_model("models.BlobMetadata")
    FileModel = apps.get_model("models.File")
    FileMetadataModel = apps.get_model("models.FileMetadata")

    async for files in _iter_files(FileModel=FileModel):
        await _process_batch(
            files,
            BlobModel=BlobModel,
            BlobMetadataModel=BlobMetadataModel,
            FileModel=FileModel,
            FileMetadataModel=FileMetadataModel,
        )


async def _iter_files(
    *, FileModel: File, batch_size: int = 1000
) -> AsyncIterator[list[File]]:
    offset = -batch_size
    while True:
        offset += batch_size
        batch = await (
            FileModel.filter(blob_id__isnull=True)
            .exclude(mediatype__name=MediaType.FOLDER)
            .select_related("namespace", "mediatype")
            .offset(offset)
            .limit(batch_size)
        )
        yield batch
        if not batch or len(batch) < batch_size:
            return


async def _process_batch(
    files,
    *,
    BlobModel: type[Blob],
    BlobMetadataModel: type[BlobMetadata],
    FileModel: type[File],
    FileMetadataModel: type[FileMetadata],
) -> None:
    file_ids = [file.id for file in files]
    metadata_by_file_id = {
        row["file_id"]: row["data"]
        for row in await FileMetadataModel.filter(
            file_id__in=file_ids,
        ).values("file_id", "data")
    }

    blobs = []
    blob_metadata = []
    for file in files:
        blob_id = uuid.uuid7()
        blobs.append(
            BlobModel(
                id=blob_id,
                storage_key=_storage_key(file.namespace.path, file.path),
                size=file.size,
                chash=file.chash,
                media_type=file.mediatype.name,
                created_at=file.modified_at,
            )
        )
        file.blob_id = blob_id

        metadata = metadata_by_file_id.get(file.id)
        if metadata is not None:
            blob_metadata.append(
                BlobMetadataModel(
                    id=uuid.uuid7(),
                    blob_id=blob_id,
                    data=metadata,
                )
            )
    if blobs:
        await BlobModel.bulk_create(blobs)
        await FileModel.bulk_update(files, fields=["blob_id"])
    if blob_metadata:
        await BlobMetadataModel.bulk_create(blob_metadata)


class Migration(migrations.Migration):
    dependencies = [("models", "0008_auto_20260501_1941")]

    initial = False

    operations = [
        ops.RunPython(
            backfill_files_to_blobs,
            reverse_code=ops.RunPython.noop,
        ),
    ]
