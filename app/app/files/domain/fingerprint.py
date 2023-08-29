from __future__ import annotations

from typing import Any, ClassVar
from uuid import UUID

__all__ = ["Fingerprint"]


class FingerprintAlreadyExists(Exception):
    pass


class FingerprintNotFound(Exception):
    pass


class Fingerprint:
    __slots__ = ("file_id", "value")

    AlreadyExists: ClassVar[type[Exception]] = FingerprintAlreadyExists
    NotFound: ClassVar[type[Exception]] = FingerprintNotFound

    def __init__(self, file_id: UUID, value: int):
        self.file_id = file_id
        self.value = value

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Fingerprint):
            return NotImplemented

        return self.file_id == other.file_id and self.value == other.value

    def __hash__(self) -> int:
        return hash((self.file_id, self.value))

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"file_id={self.file_id!r}, "
            f"value={self.value!r}"
            ")"
        )
