from __future__ import annotations

from typing import Protocol

from app.domain.entities import User


class IUserRepository(Protocol):
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
