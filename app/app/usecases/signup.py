from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.app.services import NamespaceService, UserService
    from app.domain.entities import User

__all__ = ["SignUp"]


class SignUp:
    def __init__(self, namespace_service: NamespaceService, user_service: UserService):
        self.namespace_service = namespace_service
        self.user_service = user_service

    async def __call__(
        self,
        username: str,
        password: str,
        storage_quota: int | None = None,
    ) -> User:
        """
        Creates a new user and setups a default namespace.

        Args:
            username (str): Username for a new user.
            password (str): Plain-text password.
            storage_quota (int | None, optional): Storage quota for the account.
                Use None for the unlimited quota. Defaults to None.

        Raises:
            UserAlreadyExists: If user with a username already exists.

        Returns:
            User: A freshly created user.
        """
        user = await self.user_service.create(
            username,
            password,
            storage_quota=storage_quota,
        )
        await self.namespace_service.create(user.username, owner_id=user.id)
        return user
