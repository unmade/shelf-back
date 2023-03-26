from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.app.managers import NamespaceManager
    from app.app.services import UserService
    from app.app.users.domain import User

__all__ = ["SignUp"]


class SignUp:
    __slots__ = ["ns_manager", "user_service"]

    def __init__(self, ns_manager: NamespaceManager, user_service: UserService):
        self.ns_manager = ns_manager
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
        await self.ns_manager.create_namespace(user.username, owner_id=user.id)
        return user
