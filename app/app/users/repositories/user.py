from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypedDict, Unpack

from app.app.users.domain import User

if TYPE_CHECKING:
    from uuid import UUID

    from app.typedefs import StrOrUUID


class UserUpdate(TypedDict, total=False):
    email: str
    email_verified: bool


class IUserRepository(Protocol):
    async def exists_with_email(self, email: str) -> bool:
        """Returns True if user with the specified email exists, otherwise False."""

    async def get_by_username(self, username: str) -> User:
        """
        Retrieves a user by username

        Raises:
            User.NotFound: If User with a target username does not exist.
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
            User.AlreadyExists: If user with a target username already exist.
        """

    async def update(self, user_id: UUID, **fields: Unpack[UserUpdate]) -> User:
        """Updates user with provided fields."""
