from __future__ import annotations

from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from app import security
from app.app.infrastructure.database import IDatabase
from app.app.repositories import IAccountRepository, IUserRepository
from app.app.users.domain import SENTINEL_ID, Account, User

if TYPE_CHECKING:
    from app.typedefs import StrOrUUID

__all__ = ["UserService"]


class IServiceDatabase(IDatabase, Protocol):
    account: IAccountRepository
    user: IUserRepository


class UserService:
    def __init__(self, database: IServiceDatabase):
        self.db = database

    async def add_bookmark(self, user_id: StrOrUUID, file_id: StrOrUUID) -> None:
        """
        Adds a file to user bookmarks.

        Args:
            user_id (StrOrUUID): Target user ID.
            file_id (StrOrUUID): Target file ID.

        Raises:
            User.NotFound: If User with a target user_id does not exist.
            File.NotFound: If File with a target file_id does not exist.
        """
        await self.db.user.add_bookmark(user_id=user_id, file_id=file_id)

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

    async def list_bookmarks(self, user_id: StrOrUUID) -> list[UUID]:
        """
        Lists bookmarks for a given user ID.

        Args:
            user_id (str): User ID to list bookmarks for.

        Raises:
            User.NotFound: If User with given ID does not exist.

        Returns:
            list[UUID]: List of resource IDs bookmarked by user.
        """
        return await self.db.user.list_bookmarks(user_id)

    async def remove_bookmark(self, user_id: StrOrUUID, file_id: StrOrUUID) -> None:
        """
        Removes a file from user bookmarks.

        Args:
            user_id (StrOrUUID): Target user ID.
            file_id (StrOrUUID): Target file ID.

        Raises:
            User.NotFound: If User with a target user_id does not exists.
        """
        await self.db.user.remove_bookmark(user_id, file_id)

    async def verify_credentials(self, username: str, password: str) -> User | None:
        """
        Verifies user credentials and returns a User instance.

        Args:
            username (str): User username.
            password (str): User plaint-text password.

        Returns:
            bool: a User instance if credentials are valid, None otherwise.
        """
        try:
            user = await self.db.user.get_by_username(username.lower().strip())
        except User.NotFound:
            return None
        if not security.verify_password(password, user.password):
            return None
        return user
