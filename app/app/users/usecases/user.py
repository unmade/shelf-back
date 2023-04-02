from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from app.app.files.domain import File

if TYPE_CHECKING:
    from app.app.files.services import FileCoreService, NamespaceService
    from app.app.users.domain import Account, Bookmark, User
    from app.app.users.services import BookmarkService, UserService
    from app.typedefs import StrOrUUID


class AccountSpaceUsage(NamedTuple):
    used: int
    quota: int | None


class UserUseCase:
    __slots__ = ["bookmark_service", "filecore", "ns_service", "user_service"]

    def __init__(
        self,
        bookmark_service: BookmarkService,
        filecore: FileCoreService,
        namespace_service: NamespaceService,
        user_service: UserService,
    ):
        self.bookmark_service = bookmark_service
        self.filecore = filecore
        self.ns_service = namespace_service
        self.user_service = user_service

    async def add_bookmark(self, user_id: StrOrUUID, file_id: str) -> Bookmark:
        """
        Adds a file to user bookmarks.

        Args:
            user_id (StrOrUUID): Target user ID.
            file_id (str): Target file ID.

        Returns:
            list[Bookmark]: A saved bookmark.

        Raises:
            User.NotFound: If user with a ID does not exist.
            File.NotFound: If file with a target ID does not exist.
        """
        file = await self.filecore.get_by_id(file_id)
        namespace = await self.ns_service.get_by_owner_id(user_id)
        if file.ns_path != namespace.path:
            raise File.NotFound() from None
        return await self.bookmark_service.add_bookmark(user_id, file_id)

    async def create_superuser(self, username, password) -> User:
        """
        Create a superuser with unlimited storage quote.

        Args:
            username (_type_): User username
            password (_type_): USer password

        Returns:
            User: A created superuser.
        """
        user = await self.user_service.create(username, password)
        await self.ns_service.create(user.username, owner_id=user.id)
        return user

    async def get_account(self, user_id: StrOrUUID) -> Account:
        """
        Returns an account for a given user ID.

        Args:
            user_id (StrOrUUID): User ID to return an account for.

        Raises:
            User.NotFound: If account for given user ID does not exists.

        Returns:
            Account: an Account instance.
        """
        return await self.user_service.get_account(user_id)

    async def get_account_space_usage(self, user_id: StrOrUUID) -> AccountSpaceUsage:
        """
        Returns an account for a given user ID.

        Args:
            user_id (StrOrUUID): User ID to return an account for.

        Raises:
            User.NotFound: If account for given user ID does not exists.

        Returns:
            AccountSpaceUsage: A tuple of used and total available space for account.
        """
        account = await self.user_service.get_account(user_id)
        used = await self.ns_service.get_space_used_by_owner_id(user_id)
        return AccountSpaceUsage(used=used, quota=account.storage_quota)

    async def list_bookmarks(self, user_id: StrOrUUID) -> list[Bookmark]:
        """
        Lists bookmarks for a given user ID.

        Args:
            user_id (StrOrUUID): User ID to list bookmarks for.

        Raises:
            User.NotFound: If User with given ID does not exist.

        Returns:
            list[Bookmark]: List of resource IDs bookmarked by user.
        """
        return await self.bookmark_service.list_bookmarks(user_id)

    async def remove_bookmark(self, user_id: StrOrUUID, file_id: str) -> None:
        """
        Removes a file from user bookmarks.

        Args:
            user_id (StrOrUUID): Target user ID.
            file_id (str): Target file ID.

        Raises:
            User.NotFound: If User with a target user_id does not exist.
        """
        await self.bookmark_service.remove_bookmark(user_id, file_id)
