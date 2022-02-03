from __future__ import annotations

from typing import TYPE_CHECKING

import edgedb

from app import errors

if TYPE_CHECKING:
    from app.typedefs import DBAnyConn, StrOrUUID

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
        await conn.query_single(
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
