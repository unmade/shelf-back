from __future__ import annotations

from typing import TYPE_CHECKING

import edgedb
import orjson

from app import errors

if TYPE_CHECKING:
    from collections.abc import Iterable

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


async def create(conn: DBAnyConn, file_id: StrOrUUID, fp: int) -> None:
    """
    Save file fingerprint to the database.

    The fingerprint is stored as four 16-bit parts of original fingerprint.

    Args:
        conn (DBAnyConn): Database connection.
        file_id (StrOrUUID): File to associate fingerprint with.
        fp (int): A 64-bit fingerprint.

    Raises:
        errors.FingerprintAlreadyExists: If there is already a fingerprint for a file.
        errors.FileNotFound: If a file with specified file ID doesn't exist.
    """

    query = """
        INSERT Fingerprint {
            part1 := <int32>$part1,
            part2 := <int32>$part2,
            part3 := <int32>$part3,
            part4 := <int32>$part4,
            file := (
                SELECT File
                FILTER .id = <uuid>$file_id
                LIMIT 1
            )
        }
    """

    parts = _split_int8_by_int2(fp)

    try:
        await conn.query_required_single(
            query,
            file_id=file_id,
            part1=parts[0],
            part2=parts[1],
            part3=parts[2],
            part4=parts[3],
        )
    except edgedb.ConstraintViolationError as exc:
        raise errors.FingerprintAlreadyExists() from exc
    except edgedb.MissingRequiredError as exc:
        raise errors.FileNotFound() from exc


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
