from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Protocol, TypeAlias

if TYPE_CHECKING:
    from app.domain.entities import Fingerprint
    from app.typedefs import StrOrPath

    MatchResult: TypeAlias = dict[Fingerprint, list[Fingerprint]]


class IFingerprintRepository(Protocol):
    async def intersect_all_with_prefix(
        self, ns_path: StrOrPath, prefix: StrOrPath
    ) -> MatchResult:
        """
        Finds all approximately matching fingerprints for files with path starting with
        given prefix.

        Args:
            ns_path (StrOrPath): Target namespace.
            path (StrOrPath): Folder path where to intersect fingerprints.

        Returns:
            MatchResult: Adjacency list containing fingerprints.
        """

    async def save(self, fingerprint: Fingerprint) -> Fingerprint:
        """
        Saves file fingerprint to the database.

        Args:
            fingerprint (Fingerprint): File fingerprint.

        Raises:
            errors.FingerprintAlreadyExists: If fingerprint for a file already exists.
            errors.FileNotFound: If a file with specified file ID doesn't exist.
        """

    async def save_batch(self, fingerprints: Iterable[Fingerprint]) -> None:
        """
        Save multiple fingerprints at once.

        Args:
            fingerprints (Iterable[Fingerprint]): Iterable of fingerprints to save.
        """
