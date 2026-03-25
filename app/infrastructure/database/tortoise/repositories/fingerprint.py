from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise.exceptions import IntegrityError

from app.app.files.domain import File, Fingerprint
from app.app.files.repositories import IFingerprintRepository
from app.infrastructure.database.tortoise import models

if TYPE_CHECKING:
    from collections.abc import Iterable

    from app.app.files.domain import AnyPath
    from app.app.files.repositories.fingerprint import MatchResult

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


def _from_db(obj: models.Fingerprint) -> Fingerprint:
    value = _join_int2(obj.part4, obj.part3, obj.part2, obj.part1)
    return Fingerprint(
        file_id=obj.file_id,  # type: ignore[attr-defined]
        value=value,
    )


class FingerprintRepository(IFingerprintRepository):
    async def intersect_all_with_prefix(
        self, ns_path: AnyPath, prefix: AnyPath
    ) -> MatchResult:
        prefix_str = str(prefix)

        fingerprints = await (
            models.Fingerprint
            .filter(
                file__namespace__path=str(ns_path),
                file__path__startswith=prefix_str,
            )
            .select_related("file")
        )

        if not fingerprints:
            return {}

        result: MatchResult = {}
        for fp in fingerprints:
            dupes: list[Fingerprint] = []
            for other in fingerprints:
                if other.file_id == fp.file_id:  # type: ignore[attr-defined]
                    continue
                if (
                    other.part1 == fp.part1
                    or other.part2 == fp.part2
                    or other.part3 == fp.part3
                    or other.part4 == fp.part4
                ):
                    dupes.append(_from_db(other))
            if dupes:
                result[_from_db(fp)] = dupes

        return result

    async def save(self, fingerprint: Fingerprint) -> Fingerprint:
        parts = _split_int8_by_int2(fingerprint.value)
        try:
            await models.Fingerprint.create(
                file_id=fingerprint.file_id,
                part1=parts[0],
                part2=parts[1],
                part3=parts[2],
                part4=parts[3],
            )
        except IntegrityError as exc:
            err_msg = str(exc).lower()
            if "unique" in err_msg:
                raise Fingerprint.AlreadyExists() from exc
            raise File.NotFound() from exc
        return fingerprint

    async def save_batch(self, fingerprints: Iterable[Fingerprint]) -> None:
        objs = [
            models.Fingerprint(
                file_id=fp.file_id,
                part1=parts[0],
                part2=parts[1],
                part3=parts[2],
                part4=parts[3],
            )
            for fp in fingerprints
            for parts in [_split_int8_by_int2(fp.value)]
        ]

        try:
            await models.Fingerprint.bulk_create(objs, ignore_conflicts=True)
        except IntegrityError as exc:
            raise File.NotFound() from exc
