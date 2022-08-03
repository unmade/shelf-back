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


async def intersect_in_folder(
    conn: DBAnyConn,
    namespace: StrOrPath,
    path: StrOrPath,
) -> dict[Fingerprint, list[Fingerprint]]:
    """
    Find all approximately matching fingerprints for each f-print in the given folder.

    The resulting intersection also includes sub-folders.

    Args:
        conn (DBAnyConn): Database connection.
        namespace (StrOrPath): Target namespace.
        path (StrOrPath): Folder path where to intersect fingerprints.

    Returns:
        dict[Fingerprint, list[Fingerprint]]: Adjacency list containing fingerprints.
    """

    query = """
        WITH
            Duplicate := Fingerprint,
        SELECT
            Fingerprint {
                part1,
                part2,
                part3,
                part4,
                file: { id },
                dupes := (
                    SELECT
                        Duplicate { part1, part2, part3, part4, file: { id } }
                    FILTER
                        Duplicate.file.namespace.path = <str>$ns_path
                        AND
                        Duplicate.file.path LIKE <str>$path ++ '%'
                        AND
                        Duplicate.file != Fingerprint.file
                        AND
                        (
                            Duplicate.part1 = Fingerprint.part1
                            OR
                            Duplicate.part2 = Fingerprint.part2
                            OR
                            Duplicate.part3 = Fingerprint.part3
                            OR
                            Duplicate.part4 = Fingerprint.part4
                        )
                ),
            }
        FILTER
            .file.namespace.path = <str>$ns_path
            AND
            .file.path LIKE <str>$path ++ '%'
            AND
            count(.dupes) > 0
    """

    path = "" if path == "." else f"{path}/"
    fingerprints = await conn.query(query, ns_path=str(namespace), path=str(path))

    return {
        from_db(fp): [from_db(dupe) for dupe in fp.dupes]
        for fp in fingerprints
    }
