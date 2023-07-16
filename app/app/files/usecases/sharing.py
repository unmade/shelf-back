from __future__ import annotations

from typing import TYPE_CHECKING, cast

from app.app.files.domain import AnyFile, FileMember

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.files.domain import AnyPath, File, SharedLink
    from app.app.files.services import FileMemberService, FileService, SharingService
    from app.app.users.services import UserService

__all__ = ["SharingUseCase"]


class SharingUseCase:
    __slots__ = ["file", "file_member", "sharing", "user"]

    def __init__(
        self,
        file_service: FileService,
        file_member: FileMemberService,
        sharing: SharingService,
        user: UserService,
    ):
        self.file = file_service
        self.file_member = file_member
        self.sharing = sharing
        self.user = user

    async def add_member(self, ns_path: str, file_id: str, username: str) -> FileMember:
        """
        Adds a user with a given username to a file members.

        Raises:
            File.AlreadyExists: If the file name already taken in the target folder.
            File.IsMounted: If the target folder is a mounted one.
            File.MalformedPath: If file and target folder are in the same namespace.
            File.MissingParent: If folder does not exist.
            File.NotFound: If file with a given ID does not exist.
            FileMember.AlreadyExists: If user already a member of the target file.
            User.NotFound: If User with a target username does not exist.
        """
        # todo: check file belongs to the namespace
        user = await self.user.get_by_username(username)
        access_level = FileMember.AccessLevel.editor
        member = await self.file_member.add(file_id, user.id, access_level=access_level)
        await self.file.mount(file_id, at_folder=(user.username, "."))
        return member

    async def create_link(self, ns_path: str, path: AnyPath) -> SharedLink:
        file = await self.file.get_at_path(ns_path, path)
        return await self.sharing.create_link(file.id)

    async def get_link(self, ns_path: str, path: AnyPath) -> SharedLink:
        file = await self.file.get_at_path(ns_path, path)
        return await self.sharing.get_link_by_file_id(file.id)

    async def get_link_thumbnail(
        self, token: str, *, size: int
    ) -> tuple[AnyFile, bytes]:
        link = await self.sharing.get_link_by_token(token)
        return cast(
            tuple[AnyFile, bytes],
            await self.file.thumbnail(link.file_id, size=size)
        )

    async def list_members(self, ns_path: str, file_id: str) -> list[FileMember]:
        return await self.file_member.list_all(file_id)

    async def get_shared_item(self, token: str) -> File:
        link = await self.sharing.get_link_by_token(token)
        return await self.file.filecore.get_by_id(link.file_id)

    async def remove_member(self, file_id: str, user_id: UUID) -> None:
        await self.file_member.remove(file_id, user_id)

    async def revoke_link(self, token: str) -> None:
        await self.sharing.revoke_link(token)
