from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

import edgedb
import orjson

from app.app.files.domain import File, Fingerprint
from app.app.repositories import IFingerprintRepository

if TYPE_CHECKING:
    from app.app.repositories.fingerprint import MatchResult
    from app.infrastructure.database.edgedb.typedefs import EdgeDBAnyConn, EdgeDBContext
    from app.typedefs import StrOrPath

__all__ = ["FingerprintRepository"]

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
    """Join 16-bit integers into one integer."""
    result = integers[0]
    for x in integers[1:]:
        result = result << 16 | x
    return result


def from_db(obj) -> Fingerprint:
    value = _join_int2(obj.part4, obj.part3, obj.part2, obj.part1)
    return Fingerprint(obj.file.id, value)


class FingerprintRepository(IFingerprintRepository):
    def __init__(self, db_context: EdgeDBContext):
        self.db_context = db_context

    @property
    def conn(self) -> EdgeDBAnyConn:
        return self.db_context.get()

    async def intersect_all_with_prefix(
        self, ns_path: StrOrPath, prefix: StrOrPath
    ) -> MatchResult:
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
                            Duplicate.file.path LIKE <str>$prefix ++ '%'
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
                .file.path LIKE <str>$prefix ++ '%'
                AND
                count(.dupes) > 0
        """

        fingerprints = await self.conn.query(
            query, ns_path=str(ns_path), prefix=str(prefix)
        )

        return {
            from_db(fp): [from_db(dupe) for dupe in fp.dupes]
            for fp in fingerprints
        }

    async def save(self, fingerprint: Fingerprint) -> Fingerprint:
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

        parts = _split_int8_by_int2(fingerprint.value)

        try:
            await self.conn.query_required_single(
                query,
                file_id=fingerprint.file_id,
                part1=parts[0],
                part2=parts[1],
                part3=parts[2],
                part4=parts[3],
            )
        except edgedb.ConstraintViolationError as exc:
            raise Fingerprint.AlreadyExists() from exc
        except edgedb.MissingRequiredError as exc:
            raise File.NotFound() from exc

        return fingerprint

    async def save_batch(self, fingerprints: Iterable[Fingerprint]) -> None:
        query = """
            WITH
                fingerprints := array_unpack(<array<json>>$fingerprints),
            FOR fp IN {fingerprints}
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
                            .id = <uuid>fp['file_id']
                    )
                }
                UNLESS CONFLICT
            )
        """

        data = []
        for fingerprint in fingerprints:
            parts = _split_int8_by_int2(fingerprint.value)
            data.append(
                orjson.dumps({
                    "file_id": str(fingerprint.file_id),
                    "part1": parts[0],
                    "part2": parts[1],
                    "part3": parts[2],
                    "part4": parts[3],
                }).decode()
            )

        try:
            await self.conn.query(query, fingerprints=data)
        except edgedb.MissingRequiredError as exc:
            raise File.NotFound() from exc
