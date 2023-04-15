from __future__ import annotations

from typing import Protocol

__all__ = ["ITokenRepository"]


class ITokenRepository(Protocol):
    async def delete(self, key: str) -> bool:
        """
        Deletes token by key.

        Args:
            key (str): A key, typically a token family ID.

        Returns:
            bool: True if token was deleted, False otherwise.
        """

    async def get(self, key: str) -> str | None:
        """
        Retrieves a token by its key.

        Args:
            key (str): A key, typically a token family ID.

        Returns:
            str | None: Token if it exists, otherwise None.
        """

    async def set(self, key: str, value: str) -> bool:
        """
        Stores token by some key.

        Args:
            key (str): A key, typically a token family ID.
            value (str): A token
        """
