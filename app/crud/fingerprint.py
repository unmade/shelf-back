from __future__ import annotations

from typing import TYPE_CHECKING

import edgedb
import orjson

from app import errors
from app.entities import Fingerprint

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from app.typedefs import DBAnyConn, StrOrPath, StrOrUUID

_MASK = 0xFFFF


def _split_int8_by_int2(integer: int) -> tuple[int, int, int, int]:
    """Split a 64-bit integer to four 16-bit ones."""
    return (
        (integer) & _MASK,
        (integer >> 16) & _MASK,
        (integer >> 32) & _MASK,
        (integer >> 48) & _MASK,
    )


def _join_int2(*integers: int) -> int:
    """Join 16-bit integers to one integer."""
    result = integers[0]
    for x in integers[1:]:
        result = result << 16 | x
    return result


def from_db(obj: edgedb.Object) -> Fingerprint:
    value = _join_int2(obj.part4, obj.part3, obj.part2, obj.part1)
    return Fingerprint(obj.file.id, value)


async def create_batch(
    conn: DBAnyConn,
    namespace: StrOrPath,
    fingerprints: Iterable[tuple[StrOrPath, int] | None],
) -> None:
    """
    Create fingerprints for multiple files in the same namespace at once.

    Args:
        conn (DBAnyConn): Database connection.
        namespace (StrOrPath): Files namespace.
        fingerprints (Iterable[tuple[StrOrPath, int]): Tuple, where the first element
            is a file path, and the second one is a fingerprint.

    Raises:
        errors.FingerprintAlreadyExists: If fingerprints for a file already exists.
        errors.FileNotFound: If file not found in a given namespace.
    """

    query = """
        WITH
            fingerprints := array_unpack(<array<json>>$fingerprints),
            namespace := (
                SELECT
                    Namespace
                FILTER
                    .path = <str>$ns_path
                LIMIT 1
            ),
        FOR fp in {fingerprints}
        UNION (
            INSERT Fingerprint {
                part1 := <int32>fp['part1'],
                part2 := <int32>fp['part2'],
                part3 := <int32>fp['part3'],
                part4 := <int32>fp['part4'],
                file := (
                    SELECT
                        File
                    FILTER
                        .namespace = namespace
                        AND
                        .path = <str>fp['path']
                    LIMIT 1
                )
            }
        )
    """

    data = []
    fingerprints = (fp for fp in fingerprints if fp is not None)
    for path, fingerprint in fingerprints:  # type: ignore
        parts = _split_int8_by_int2(fingerprint)
        data.append(
            orjson.dumps({
                "path": str(path),
                "part1": parts[0],
                "part2": parts[1],
                "part3": parts[2],
                "part4": parts[3],
            }).decode()
        )

    try:
        await conn.query(query, ns_path=str(namespace), fingerprints=data)
    except edgedb.ConstraintViolationError as exc:
        raise errors.FingerprintAlreadyExists() from exc
    except edgedb.MissingRequiredError as exc:
        raise errors.FileNotFound() from exc


async def delete_batch(conn: DBAnyConn, file_ids: Sequence[StrOrUUID]) -> None:
    """
    Delete Fingerprints with given file IDs.

    Args:
        conn (DBAnyConn): Database connection.
        file_ids (Sequence[StrOrUUID]): sequence of file IDs for which fingerprints
            should be deleted.
    """
    query = """
        DELETE
            Fingerprint
        FILTER
            .file.id IN {array_unpack(<array<uuid>>$file_ids)}
    """

    await conn.query(query, file_ids=file_ids)


async def get(conn: DBAnyConn, file_id: StrOrUUID) -> Fingerprint:
    """
    Return Fingerprint for a given file ID.

    Args:
        conn (DBAnyConn): Database connection.
        file_id (StrOrUUID): Target file ID.

    Raises:
        errors.FingerprintNotFound: If fingerprint for a given file ID does not exists.

    Returns:
        Fingerprint: Fingerprint for a given file ID.
    """
    query = """
        SELECT
            Fingerprint { part1, part2, part3, part4, file: { id } }
        FILTER
            .file.id = <uuid>$file_id
        LIMIT 1
    """

    try:
        return from_db(await conn.query_required_single(query, file_id=file_id))
    except edgedb.NoDataError as exc:
        raise errors.FingerprintNotFound() from exc
