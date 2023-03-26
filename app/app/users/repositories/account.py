from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.app.users.domain import Account

if TYPE_CHECKING:
    from app.typedefs import StrOrUUID


class IAccountRepository(Protocol):
    async def get_by_user_id(self, user_id: StrOrUUID) -> Account:
        """
        Returns an account for a given user ID.

        Args:
            user_id (StrOrUUID): User ID to return an account for.

        Raises:
            User.NotFound: If account for given user ID does not exists.

        Returns:
            Account: an Account instance.
        """

    async def save(self, account: Account) -> Account:
        """
        Saves new account for a user.

        Args:
            account (Account): account instance to save.

        Raises:
            User.AlreadyExists: If email is already taken.

        Returns:
            Account: Created account.
        """
