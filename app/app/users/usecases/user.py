from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple, Protocol
from uuid import UUID

from app.app.users.domain import User
from app.cache import cache

if TYPE_CHECKING:
    from collections.abc import Iterable

    from app.app.files.services import FileService, NamespaceService
    from app.app.infrastructure.database import IAtomic
    from app.app.users.domain import Account, Bookmark
    from app.app.users.services import BookmarkService, UserService

    class IUseCaseServices(IAtomic, Protocol):
        bookmark: BookmarkService
        file: FileService
        namespace: NamespaceService
        user: UserService

__all__ = [
    "AccountSpaceUsage",
    "EmailUpdateLimitReached",
    "UserUseCase",
]


class AccountSpaceUsage(NamedTuple):
    used: int
    quota: int | None


class EmailUpdateLimitReached(Exception):
    pass


class UserUseCase:
    __slots__ = [
        "_services", "bookmark_service", "file_service", "ns_service", "user_service"
    ]

    def __init__(self, services: IUseCaseServices):
        self._services = services
        self.bookmark_service = services.bookmark
        self.file_service = services.file
        self.ns_service = services.namespace
        self.user_service = services.user

    async def add_bookmark_batch(self, user_id: UUID, file_ids: Iterable[UUID]) -> None:
        """Adds multiple files to user bookmarks"""
        namespace = await self.ns_service.get_by_owner_id(user_id)
        files = await self.file_service.get_by_id_batch(namespace.path, file_ids)
        return await self.bookmark_service.add_batch(
            user_id,
            file_ids=[file.id for file in files],
        )

    async def change_email_complete(self, user_id: UUID, code: str) -> bool:
        """
        Completes the process of changing email.

        Raises:
            EmailUpdateNotStarted: If process of changing email hasn't been started.
        """
        completed = await self.user_service.change_email_complete(user_id, code)
        await cache.set(f"change_email:{user_id}:completed", 1, expire="6h")
        return completed

    async def change_email_resend_code(self, user_id: UUID) -> None:
        """
        Resends the verification code to the new email.

        Raises:
            EmailUpdateNotStarted: If process of changing email hasn't been started.
            OTPCodeAlreadySent: If previous OTP code hasn't expired yet.
        """
        await self.user_service.change_email_resend_code(user_id)

    async def change_email_start(self, user_id: UUID, email: str) -> None:
        """
        Starts the process of changing user email and sends verification code to the
        provided email. At this point it doesn't change email in the DB.

        Raises:
            EmailUpdateAlreadyStarted: If email update already started.
            EmailUpdateLimitReached: If user tries to change email frequently.
            User.AlreadyExists: If user with provided email already exists.
        """
        if await cache.exists(f"change_email:{user_id}:completed"):
            raise EmailUpdateLimitReached() from None
        await self.user_service.change_email_start(user_id, email)

    async def create_superuser(self, username: str, password: str) -> User:
        """
        Create a superuser with unlimited storage quote.

        Raises:
            Namespace.AlreadyExists: If namespace with a given `path` already exists.
            User.AlreadyExists: If user with a username already exists.
        """
        async for tx in self._services.atomic():
            async with tx:
                user = await self.user_service.create(
                    username, password, superuser=True
                )
                await self.ns_service.create(user.username, owner_id=user.id)
        return user

    async def get_account(self, user_id: UUID) -> Account:
        """
        Returns an account for a given user ID.

        Raises:
            User.NotFound: If account for given user ID does not exists.
        """
        return await self.user_service.get_account(user_id)

    async def get_account_space_usage(self, user_id: UUID) -> AccountSpaceUsage:
        """
        Returns an account for a given user ID.

        Raises:
            User.NotFound: If account for given user ID does not exists.
        """
        account = await self.user_service.get_account(user_id)
        used = await self.ns_service.get_space_used_by_owner_id(user_id)
        return AccountSpaceUsage(used=used, quota=account.storage_quota)

    async def list_bookmarks(self, user_id: UUID) -> list[Bookmark]:
        """
        Lists bookmarks for a given user ID.

        Raises:
            User.NotFound: If User with given ID does not exist.
        """
        return await self.bookmark_service.list_bookmarks(user_id)

    async def remove_bookmark_batch(
        self, user_id: UUID, file_ids: Iterable[UUID]
    ) -> None:
        """Removes multiple files from user bookmarks."""
        return await self.bookmark_service.remove_batch(user_id, file_ids=file_ids)

    async def verify_email_send_code(self, user_id: UUID) -> None:
        """
        Sends verification code to the user current email.

        Raises:
            OTPCodeAlreadySent: If previous OTP code hasn't expired yet.
            User.EmailAlreadyVerified: If user email already verified.
            User.EmailIsMissing: If user doesn't have email.
            User.NotFound: If user with specified ID does not exist.
        """
        await self.user_service.verify_email_send_code(user_id)

    async def verify_email_complete(self, user_id: UUID, code: str) -> bool:
        """Verifies user email based on provided code."""
        return await self.user_service.verify_email_complete(user_id, code)
