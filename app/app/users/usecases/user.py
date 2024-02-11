from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple, Protocol
from uuid import UUID

from app.app.users.domain import User

if TYPE_CHECKING:
    from app.app.files.services import FileService, NamespaceService
    from app.app.infrastructure.database import IAtomic
    from app.app.users.domain import Account, Bookmark
    from app.app.users.services import BookmarkService, UserService

    class IUseCaseServices(IAtomic, Protocol):
        bookmark: BookmarkService
        file: FileService
        namespace: NamespaceService
        user: UserService


class AccountSpaceUsage(NamedTuple):
    used: int
    quota: int | None


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

    async def add_bookmark(
        self, user_id: UUID, file_id: UUID, ns_path: str
    ) -> Bookmark:
        """
        Adds a file to user bookmarks.

        Raises:
            User.NotFound: If user with a ID does not exist.
            File.NotFound: If file with a target ID does not exist.
        """
        file = await self.file_service.get_by_id(ns_path, file_id)
        return await self.bookmark_service.add_bookmark(user_id, file.id)

    async def change_email_complete(self, user_id: UUID, code: str) -> bool:
        return await self.user_service.change_email_complete(user_id, code)

    async def change_email_resend_code(self, user_id: UUID) -> None:
        await self.user_service.change_email_resend_code(user_id)

    async def change_email_start(self, user_id: UUID, email: str) -> None:
        await self.user_service.change_email_start(user_id, email)

    async def create_superuser(self, username: str, password: str) -> User:
        """
        Create a superuser with unlimited storage quote.

        Raises:
            NamespaceAlreadyExists: If namespace with a given `path` already exists.
            UserAlreadyExists: If user with a username already exists.
        """
        async for tx in self._services.atomic():
            async with tx:
                user = await self.user_service.create(username, password)
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

    async def remove_bookmark(self, user_id: UUID, file_id: UUID) -> None:
        """
        Removes a file from user bookmarks.

        Raises:
            User.NotFound: If User with a target user_id does not exist.
        """
        await self.bookmark_service.remove_bookmark(user_id, file_id)

    async def send_email_verification_code(self, user_id: UUID) -> None:
        """
        Sends verification code to the email.

        Raises:
            User.EmailIsMissing: If user doesn't have email.
            User.EmailAlreadyVerified: If user email already verified.
            User.NotFound: If user with specified ID does not exist.
        """
        await self.user_service.send_email_verification_code(user_id)

    async def verify_email(self, user_id: UUID, code: str) -> bool:
        """Verifies user email based on provided code."""
        return await self.user_service.verify_email(user_id, code)
