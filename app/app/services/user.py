from __future__ import annotations

from typing import TYPE_CHECKING

from app import security
from app.domain.entities import SENTINEL_ID, Account, User

if TYPE_CHECKING:
    from app.app.repositories import IAccountRepository, IUserRepository

__all__ = ["UserService"]


class UserService:
    def __init__(
        self,
        account_repo: IAccountRepository,
        user_repo: IUserRepository,
    ):
        self.account_repo = account_repo
        self.user_repo = user_repo

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
        user = await self.user_repo.save(
            User(
                id=SENTINEL_ID,
                username=username.lower(),
                password=security.make_password(password),
                superuser=superuser,
            )
        )

        await self.account_repo.save(
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
