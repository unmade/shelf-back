from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Protocol, TypedDict, Unpack
from uuid import UUID

from app.app.users.domain import User

if TYPE_CHECKING:
    pass


class GetKwargs(TypedDict, total=False):
    id: UUID
    username: str
    email: str


class UserUpdate(TypedDict, total=False):
    email: str
    email_verified: bool
    last_login_at: datetime


class IUserRepository(Protocol):
    async def exists_with_email(self, email: str) -> bool:
        """Returns True if user with the specified email exists, otherwise False."""

    async def get(self, **fields: Unpack[GetKwargs]) -> User:
        """
        Retrieves a user if at least one of the provided matches. Normally you want to
        provide only one field.

        Raises:
            User.NotFound: If matching User does not exist.
        """

    async def save(self, user: User) -> User:
        """
        Saves a user to the database.

        Raises:
            User.AlreadyExists: If user with a target username already exist.
        """

    async def update(self, user_id: UUID, **fields: Unpack[UserUpdate]) -> User:
        """Updates user with provided fields."""
