from __future__ import annotations

from typing import Protocol

from app.domain.entities import Account


class IAccountRepository(Protocol):
    async def save(self, account: Account) -> Account:
        """
        Saves new account for a user.

        Args:
            account (Account): account instance to save.

        Raises:
            errors.UserAlreadyExists: If email is already taken.

        Returns:
            Account: Created account.
        """
