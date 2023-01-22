from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.domain.entities import Fingerprint


class IFingerprintRepository(Protocol):
    async def save(self, fingerprint: Fingerprint) -> None:
        """
        Saves file fingerprint to the database.

        Args:
            fingerprint (Fingerprint): File fingerprint.

        Raises:
            errors.FingerprintAlreadyExists: If fingerprint for a file already exists.
            errors.FileNotFound: If a file with specified file ID doesn't exist.
        """
