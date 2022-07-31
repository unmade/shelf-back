from __future__ import annotations

from typing import TYPE_CHECKING

import edgedb
import orjson

from app import errors
from app.entities import Exif, FileMetadata

if TYPE_CHECKING:
    from app.typedefs import DBAnyConn, StrOrUUID


def from_db(obj: edgedb.Object) -> FileMetadata:
    return FileMetadata(
        file_id=str(obj.file.id),
        data=orjson.loads(obj.data),
    )


async def create(conn: DBAnyConn, file_id: StrOrUUID, data: Exif) -> None:
    """
    Save file metadata to the database.

    Args:
        conn (DBAnyConn): Database connection.
        file_id (StrOrUUID): File ID to associate metadata with.
        data (Exif): Metadata.

    Raises:
        errors.FileNotFound: If a file with specified ID doesn't exist.
    """
    query = """
        INSERT FileMetadata {
            data := <json>$data,
            file := (
                SELECT File
                FILTER .id = <uuid>$file_id
                LIMIT 1
            )
        }
    """
    metadata = data.json(exclude_none=True)

    try:
        await conn.query_required_single(query, file_id=file_id, data=metadata)
    except edgedb.MissingRequiredError as exc:
        raise errors.FileNotFound() from exc


async def get(conn: DBAnyConn, file_id: StrOrUUID) -> FileMetadata:
    """
    Get metadata associated with a given File ID.

    Args:
        conn (DBAnyConn): Database connection.
        file_id (StrOrUUID): Target File ID.

    Raises:
        FileMetadataNotFound: If FileMetada for a given file ID does not exist.

    Returns:
        FileMetadata: FileMetadata.
    """
    query = """
        SELECT
            FileMetadata { data, file: { id } }
        FILTER
            .file.id = <uuid>$file_id
        LIMIT 1
    """

    try:
        return from_db(
            await conn.query_required_single(query, file_id=file_id)
        )
    except edgedb.NoDataError as exc:
        raise errors.FileMetadataNotFound() from exc
