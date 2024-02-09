from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.app.users.domain import User

if TYPE_CHECKING:
    from uuid import UUID

    from app.typedefs import StrOrUUID


class IUserRepository(Protocol):
    async def get_by_username(self, username: str) -> User:
        """
        Retrieves a user by username

        Raises:
            User.NotFound: If User with a target username does not exists.
        """

    async def get_by_id(self, user_id: StrOrUUID) -> User:
        """
        Returns a user with a given user ID.

        Raises:
            User.NotFound: If user with a target user ID does not exist.
        """

    async def save(self, user: User) -> User:
        """
        Saves a user to the database.

        Raises:
            User.AlreadyExists: If user with a target username already exists.
        """

    async def set_email_verified(self, user_id: UUID, *, verified: bool) -> None:
        """
        Sets `email_verified` for the specified user ID.
        """
