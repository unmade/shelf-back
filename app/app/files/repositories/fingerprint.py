from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterable

    from app.app.files.domain import AnyPath, Fingerprint

    type MatchResult = dict[Fingerprint, list[Fingerprint]]


class IFingerprintRepository(Protocol):
    async def intersect_all_with_prefix(
        self, ns_path: AnyPath, prefix: AnyPath
    ) -> MatchResult:
        """
        Finds all approximately matching fingerprints for files with path starting with
        given prefix.

        Args:
            ns_path (AnyPath): Target namespace.
            path (AnyPath): Folder path where to intersect fingerprints.

        Returns:
            MatchResult: Adjacency list containing fingerprints.
        """

    async def save(self, fingerprint: Fingerprint) -> Fingerprint:
        """
        Saves file fingerprint to the database.

        Args:
            fingerprint (Fingerprint): File fingerprint.

        Raises:
            Fingerprint.AlreadyExists: If fingerprint for a file already exists.
            File.NotFound: If a file with specified file ID doesn't exist.
        """

    async def save_batch(self, fingerprints: Iterable[Fingerprint]) -> None:
        """
        Save multiple fingerprints at once.

        Args:
            fingerprints (Iterable[Fingerprint]): Iterable of fingerprints to save.
        """
