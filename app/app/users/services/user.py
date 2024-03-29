from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Protocol

from pydantic import validate_email

from app.app.infrastructure import IMailBackend
from app.app.infrastructure.database import SENTINEL_ID, IDatabase
from app.app.users.domain import Account, User
from app.app.users.email import EmailVerificationMessage
from app.app.users.repositories import IAccountRepository, IUserRepository
from app.cache import cache
from app.toolkit import security, taskgroups, timezone

if TYPE_CHECKING:
    from uuid import UUID

    from app.typedefs import StrOrUUID

__all__ = [
    "EmailUpdateAlreadyStarted",
    "EmailUpdateNotStarted",
    "OTPCodeAlreadySent",
    "UserService",
]


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


class OTPCodeAlreadySent(UserServiceError):
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
        """
        Completes the process of changing email.

        Raises:
            EmailUpdateNotStarted: If process of changing email hasn't been started.
        """
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
        """
        Resends the verification code to the new email.

        Raises:
            EmailUpdateNotStarted: If process of changing email hasn't been started.
            OTPCodeAlreadySent: If previous OTP code hasn't expired yet.
        """
        email = await cache.get(f"email_update:{user_id}:email")
        if not email:
            raise EmailUpdateNotStarted() from None

        key = f"email_update:{user_id}:code"
        code = security.make_otp_code()
        if not await cache.set(key, code, expire="2m", exist=False):
            raise OTPCodeAlreadySent() from None

        user = await self.db.user.get(id=user_id)
        taskgroups.schedule(
            self._send_email_verification_code(user.display_name, email, code)
        )

    async def change_email_start(self, user_id: UUID, email: str) -> None:
        """
        Starts the process of changing user email and sends verification code to the
        provided email. At this point it doesn't change email in the DB.

        Raises:
            User.AlreadyExists: If user with provided email already exists.
            EmailUpdateAlreadyStarted: If email update already started.
        """
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

    async def get_by_id(self, user_id: UUID) -> User:
        """
        Returns a user with a given user ID.

        Raises:
            User.NotFound: If user with a target user ID does not exist.
        """
        return await self.db.user.get(id=user_id)

    async def get_by_username(self, username: str) -> User:
        """
        Retrieves a user by username.

        Raises:
            User.NotFound: If User with a target username does not exist.
        """
        return await self.db.user.get(username=username.lower().strip())

    async def signin(self, email_or_username: str, password: str) -> User:
        """
        Retrieves a user by login

        Raises:
            User.NotFound: If User with a target username does not exist.
            User.InvalidCredentials: If User password is invalid.
        """
        login = email_or_username.lower().strip()
        try:
            validate_email(login)
        except ValueError:
            user = await self.db.user.get(username=login)
        else:
            user = await self.db.user.get(email=login)

        if not user.check_password(password):
            raise User.InvalidCredentials() from None

        await self.db.user.update(user.id, last_login_at=timezone.now())
        return user

    async def verify_email_send_code(self, user_id: UUID) -> None:
        """
        Sends verification code to the user current email.

        Raises:
            OTPCodeAlreadySent: If previous OTP code hasn't expired yet.
            User.EmailAlreadyVerified: If user email already verified.
            User.EmailIsMissing: If user doesn't have email.
            User.NotFound: If user with specified ID does not exist.
        """
        user = await self.db.user.get(id=user_id)
        if not user.email:
            raise User.EmailIsMissing()

        if user.email_verified:
            raise User.EmailAlreadyVerified()

        key = _verify_email_key(user_id)
        code = security.make_otp_code()
        if not await cache.set(key, code, expire="2m", exist=False):
            raise OTPCodeAlreadySent() from None

        taskgroups.schedule(
            self._send_email_verification_code(user.display_name, user.email, code)
        )

    async def verify_email_complete(self, user_id: UUID, code: str) -> bool:
        """Verifies current user email based on provided code."""
        expected_code = await cache.get(_verify_email_key(user_id))
        if not expected_code:
            return False

        verified = secrets.compare_digest(code.encode(), expected_code.encode())
        if verified:
            await self.db.user.update(user_id, email_verified=verified)
        return verified
