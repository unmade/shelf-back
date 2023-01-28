from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.domain.entities import User

if TYPE_CHECKING:
    from uuid import UUID

    from app.typedefs import StrOrUUID


class IUserRepository(Protocol):
    async def add_bookmark(self, user_id: StrOrUUID, file_id: StrOrUUID) -> None:
        """
        Adds a file to user bookmarks.

        If file with a given file ID does not exist, then it acts as no-op.

        Args:
            user_id (StrOrUUID): Target user ID.
            file_id (StrOrUUID): Target file ID.

        Raises:
            errors.UserNotFound: If User with a target user_id does not exists.
        """

    async def get_by_username(self, username: str) -> User:
        """
        Retrieves a user by username

        Args:
            username (str): User username.

        Raises:
            errors.UserNotFound: If User with a target username does not exists.

        Returns:
            User: a User instance.
        """

    async def list_bookmarks(self, user_id: StrOrUUID) -> list[UUID]:
        """
        Lists bookmarks for a given user ID.

        Args:
            user_id (StrOrUUID): User ID to list bookmarks for.

        Raises:
            errors.UserNotFound: If User with given ID does not exist.

        Returns:
            list[UUID]: List of resource IDs bookmarked by user.
        """

    async def remove_bookmark(self, user_id: StrOrUUID, file_id: StrOrUUID) -> None:
        """
        Removes a file from user bookmarks.

        Args:
            user_id (StrOrUUID): Target user ID.
            file_id (StrOrUUID): Target file ID.

        Raises:
            errors.UserNotFound: If User with a target user_id does not exists.
        """

    async def save(self, user: User) -> User:
        """
        Saves a user to the database.

        Args:
            user (User): a user instance to create.

        Raises:
            UserAlreadyExists: If user with a target username already exists.

        Returns:
            User: a freshly created user instance.
        """
