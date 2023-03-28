from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app import security
from app.app.infrastructure.database import IDatabase
from app.app.users.domain import SENTINEL_ID, Account, User
from app.app.users.repositories import IAccountRepository, IUserRepository

if TYPE_CHECKING:
    from app.typedefs import StrOrUUID

__all__ = ["UserService"]


class IServiceDatabase(IDatabase, Protocol):
    account: IAccountRepository
    user: IUserRepository


class UserService:
    def __init__(self, database: IServiceDatabase):
        self.db = database

    async def create(
        self,
        username: str,
        password: str,
        *,
        email: str | None = None,
        first_name: str = "",
        last_name: str = "",
        superuser: bool = False,
        storage_quota: int | None = None,
    ) -> User:
        """
        Creates a new user.

        Args:
            username (str): Username for a new user.
            password (str): Plain-text password.
            email (str | None, optional): Email. Defaults to None.
            first_name (str, optional): First name. Defaults to "".
            last_name (str, optional): Last name. Defaults to "".
            superuser (bool, optional): Whether user is super user or not. Defaults to
                False.
            storage_quota (int | None, optional): Storage quota for the account.
                Use None for the unlimited quota. Defaults to None.

        Raises:
            UserAlreadyExists: If user with a username already exists.

        Returns:
            User: A freshly created user.
        """
        user = await self.db.user.save(
            User(
                id=SENTINEL_ID,
                username=username.lower(),
                password=security.make_password(password),
                superuser=superuser,
            )
        )

        await self.db.account.save(
            Account(
                id=SENTINEL_ID,
                username=username.lower(),
                email=email,
                first_name=first_name,
                last_name=last_name,
                storage_quota=storage_quota,
            )
        )
        return user

    async def get_account(self, user_id: StrOrUUID) -> Account:
        """
        Returns an account for a given user ID.

        Args:
            user_id (StrOrUUID): User ID to return an account for.

        Raises:
            User.NotFound: If account for given user ID does not exists.

        Returns:
            Account: an Account instance.
        """
        return await self.db.account.get_by_user_id(user_id)

    async def get_by_id(self, user_id: StrOrUUID) -> User:
        """
        Returns a user with a given user ID.

        Args:
            user_id (StrOrUUID): User ID to search for.

        Raises:
            User.NotFound: If user with a target user ID does not exist.

        Returns:
            User: a User instance.
        """
        return await self.db.user.get_by_id(user_id)

    async def get_by_username(self, username: str) -> User:
        """
        Retrieves a user by username

        Args:
            username (str): User username.

        Raises:
            User.NotFound: If User with a target username does not exists.

        Returns:
            User: a User instance.
        """
        return await self.db.user.get_by_username(username.lower().strip())
