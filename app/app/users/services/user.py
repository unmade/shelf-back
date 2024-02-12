from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Protocol

from app.app.infrastructure import IMailBackend
from app.app.infrastructure.database import SENTINEL_ID, IDatabase
from app.app.users.domain import Account, User
from app.app.users.email import EmailVerificationMessage
from app.app.users.repositories import IAccountRepository, IUserRepository
from app.cache import cache
from app.toolkit import security

if TYPE_CHECKING:
    from uuid import UUID

    from app.typedefs import StrOrUUID

__all__ = ["UserService"]


def _verify_email_key(user_id: UUID) -> str:
    return f"otp:verify_email:{user_id}"


class IServiceDatabase(IDatabase, Protocol):
    account: IAccountRepository
    user: IUserRepository


class UserServiceError(Exception):
    pass


class EmailUpdateAlreadyStarted(UserServiceError):
    pass


class EmailUpdateNotStarted(UserServiceError):
    pass


class UserService:
    __slots__ = ["db", "mail"]

    def __init__(self, database: IServiceDatabase, mail: IMailBackend):
        self.db = database
        self.mail = mail

    async def _send_email_verification_code(
        self, display_name: str, email: str, code: str
    ) -> None:
        message = EmailVerificationMessage(display_name, email, code)
        content = await message.build()

        async with self.mail:
            await self.mail.send(content)

    async def change_email_complete(self, user_id: UUID, code: str) -> bool:
        email, expected_code = await cache.get_many(
            f"email_update:{user_id}:email",
            f"email_update:{user_id}:code",
        )
        if not email:
            raise EmailUpdateNotStarted() from None

        if not expected_code:
            return False

        verified = secrets.compare_digest(code, expected_code)
        if verified:
            await self.db.user.update(user_id, email=email, email_verified=True)

        return verified

    async def change_email_resend_code(self, user_id: UUID) -> None:
        email = await cache.get(f"email_update:{user_id}:email")
        if not email:
            raise EmailUpdateNotStarted() from None

        user = await self.db.user.get_by_id(user_id)
        code = security.make_otp_code()
        await cache.set(f"email_update:{user_id}:code", code, expire="2m")
        await self._send_email_verification_code(user.display_name, email, code)

    async def change_email_start(self, user_id: UUID, email: str) -> None:
        if await self.db.user.exists_with_email(email):
            raise User.AlreadyExists() from None

        key = f"email_update:{user_id}:email"
        if not await cache.set(key, email, expire="10m", exist=False):
            raise EmailUpdateAlreadyStarted() from None

        await self.change_email_resend_code(user_id)

    async def create(
        self,
        username: str,
        password: str,
        *,
        email: str | None = None,
        display_name: str = "",
        superuser: bool = False,
        storage_quota: int | None = None,
    ) -> User:
        """
        Creates a new user.

        Raises:
            UserAlreadyExists: If user with a username already exists.
        """

        async for tx in self.db.atomic():
            async with tx:
                user = await self.db.user.save(
                    User(
                        id=SENTINEL_ID,
                        username=username.lower(),
                        password=security.make_password(password),
                        email=email,
                        email_verified=False,
                        display_name=display_name,
                        active=True,
                        last_login_at=None,
                        superuser=superuser,
                    )
                )
                await self.db.account.save(
                    Account(
                        id=SENTINEL_ID,
                        user_id=user.id,
                        storage_quota=storage_quota,
                    )
                )
        return user

    async def get_account(self, user_id: StrOrUUID) -> Account:
        """
        Returns an account for a given user ID.

        Raises:
            User.NotFound: If account for given user ID does not exists.
        """
        return await self.db.account.get_by_user_id(user_id)

    async def get_by_id(self, user_id: StrOrUUID) -> User:
        """
        Returns a user with a given user ID.

        Raises:
            User.NotFound: If user with a target user ID does not exist.
        """
        return await self.db.user.get_by_id(user_id)

    async def get_by_username(self, username: str) -> User:
        """
        Retrieves a user by username.

        Raises:
            User.NotFound: If User with a target username does not exist.
        """
        return await self.db.user.get_by_username(username.lower().strip())

    async def verify_email_send_code(self, user_id: UUID) -> None:
        """
        Sends verification code to the user current email.

        Raises:
            User.EmailIsMissing: If user doesn't have email.
            User.EmailAlreadyVerified: If user email already verified.
            User.NotFound: If user with specified ID does not exist.
        """
        user = await self.db.user.get_by_id(user_id)
        if not user.email:
            raise User.EmailIsMissing()

        if user.email_verified:
            raise User.EmailAlreadyVerified()

        code = security.make_otp_code()
        await cache.set(_verify_email_key(user_id), code, expire="2m")

        await self._send_email_verification_code(user.display_name, user.email, code)

    async def verify_email_complete(self, user_id: UUID, code: str) -> bool:
        """Verifies user email based on provided code."""
        expected_code = await cache.get(_verify_email_key(user_id), default="")
        verified = secrets.compare_digest(code.encode(), expected_code.encode())
        if verified:
            await self.db.user.update(user_id, email_verified=verified)
        return verified
