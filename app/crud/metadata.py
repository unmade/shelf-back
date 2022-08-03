from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, cast

import edgedb
import orjson

from app import errors
from app.entities import Exif, FileMetadata

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.typedefs import DBAnyConn, StrOrPath, StrOrUUID


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


async def create_batch(
    conn: DBAnyConn,
    namespace: StrOrPath,
    data: Iterable[tuple[StrOrPath, Exif | None]],
):
    """
    Create metadata for multiple files in the same namespace at once.

    Args:
        conn (DBAnyConn): Database connection.
        namespace (StrOrPath): Files namespace.
        data (tuple[StrOrPath, FileMetadata]): Sequence of tuples, where the first item
            is a file path, and the second one is a FileMetadata.
    """

    query = """
        WITH
            entries := array_unpack(<array<json>>$entries),
            namespace := (
                SELECT
                    Namespace
                FILTER
                    .path = <str>$ns_path
                LIMIT 1
            ),
        FOR entry in {entries}
        UNION (
            INSERT FileMetadata {
                data := entry['data'],
                file := (
                    SELECT
                        File
                    FILTER
                        .namespace = namespace
                        AND
                        .path = <str>entry['path']
                    LIMIT 1
                )
            }
        )
    """

    entries = [
        orjson.dumps({
            "path": str(path),
            "data": meta.dict(exclude_none=True),
        }).decode()
        for path, meta in data
        if meta is not None
    ]

    try:
        await conn.query(query, ns_path=str(namespace), entries=entries)
    except edgedb.ConstraintViolationError as exc:
        raise errors.FileMetadataAlreadyExists() from exc
    except edgedb.MissingRequiredError as exc:
        raise errors.FileNotFound() from exc


async def delete_batch(conn: DBAnyConn, file_ids: Sequence[StrOrUUID]) -> None:
    """
    Delete FileMetada with given file IDs.

    Args:
        conn (DBAnyConn): Database connection.
        file_ids (Sequence[StrOrUUID]): sequence of file IDs for which metadata
            should be deleted.
    """
    query = """
        DELETE
            FileMetadata
        FILTER
            .file.id IN {array_unpack(<array<uuid>>$file_ids)}
    """

    await conn.query(query, file_ids=file_ids)


async def exists(conn: DBAnyConn, file_id: StrOrUUID) -> bool:
    """
    Check whether a file or a folder exists in a target path.

    Args:
        conn (DBAnyConn): Database connection.
        file_id (StrOrUUID): Target file ID.

    Returns:
        bool: True if file metadata exists, False otherwise.
    """
    query = """
        SELECT EXISTS(
            SELECT
                FileMetadata
            FILTER
                .file.id = <uuid>$file_id
        )
    """

    return cast(
        bool,
        await conn.query_required_single(query, file_id=file_id)
    )


async def get(conn: DBAnyConn, file_id: StrOrUUID) -> FileMetadata:
    """
    Get metadata associated with a given File ID.

    Args:
        conn (DBAnyConn): Database connection.
        file_id (StrOrUUID): Target File ID.

    Raises:
        FileMetadataNotFound: If FileMetada for a given file ID does not exist.

    Returns:
        FileMetadata: FileMetadata
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
