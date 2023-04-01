from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.app.users.domain import User

if TYPE_CHECKING:

    from app.typedefs import StrOrUUID


class IUserRepository(Protocol):
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

    async def save(self, user: User) -> User:
        """
        Saves a user to the database.

        Args:
            user (User): a user instance to create.

        Raises:
            User.AlreadyExists: If user with a target username already exists.

        Returns:
            User: a freshly created user instance.
        """
