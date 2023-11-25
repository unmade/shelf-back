from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, cast

from app.app.files.domain import AnyFile, File, FileMember

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.files.domain import AnyPath, SharedLink
    from app.app.files.domain.file_member import FileMemberActions
    from app.app.files.services import (
        FileMemberService,
        FileService,
        NamespaceService,
        SharingService,
    )
    from app.app.users.services import UserService

__all__ = ["SharingUseCase"]


class SharingUseCase:
    __slots__ = ["file", "file_member", "namespace", "sharing", "user"]

    def __init__(
        self,
        file_service: FileService,
        file_member: FileMemberService,
        namespace: NamespaceService,
        sharing: SharingService,
        user: UserService,
    ):
        self.file = file_service
        self.file_member = file_member
        self.namespace = namespace
        self.sharing = sharing
        self.user = user

    async def add_member(
        self, ns_path: str, file_id: UUID, username: str
    ) -> FileMember:
        """
        Adds a user with a given username to a file members.

        Raises:
            File.ActionNotAllowed: If adding a file member is not allowed.
            File.AlreadyExists: If the file name already taken in the target folder.
            File.IsMounted: If the target folder is a mounted one.
            File.MalformedPath: If file and target folder are in the same namespace.
            File.MissingParent: If folder does not exist.
            File.NotFound: If file with a given ID does not exist.
            FileMember.AlreadyExists: If user already a member of the target file.
            Namespace.NotFound: If namespace given namespace does not exist.
            User.NotFound: If User with a target username does not exist.
        """
        file = await self.file.get_by_id(ns_path, file_id)
        if not file.can_reshare():
            raise File.ActionNotAllowed()

        if ns_path == file.ns_path:
            namespace = await self.namespace.get_by_path(ns_path)
            with contextlib.suppress(FileMember.AlreadyExists):
                await self.file_member.add(
                    file_id, namespace.owner_id, actions=FileMember.OWNER
                )

        user = await self.user.get_by_username(username)
        member = await self.file_member.add(file_id, user.id, actions=FileMember.EDITOR)
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

    async def list_members(self, ns_path: str, file_id: UUID) -> list[FileMember]:
        """
        Lists all file members including file owner for a given file.

        If a file member doesn't have a permission to view a file, then the result
        will have only that member and no one else.

        Raises:
            File.ActionNotAllowed: If listing file members is not allowed.
            File.NotFound: If file with a given ID does not exist.
            Namespace.NotFound: If namespace with a target path does not exist.
        """
        with contextlib.suppress(File.ActionNotAllowed):
            file = await self.file.get_by_id(ns_path, file_id)
            return await self.file_member.list_all(file.id)

        namespace = await self.namespace.get_by_path(ns_path)
        try:
            member = await self.file_member.get(file_id, namespace.owner_id)
        except FileMember.NotFound as exc:
            raise File.ActionNotAllowed() from exc

        return [member]

    async def get_shared_item(self, token: str) -> File:
        link = await self.sharing.get_link_by_token(token)
        return await self.file.filecore.get_by_id(link.file_id)

    async def remove_member(self, ns_path: str, file_id: UUID, user_id: UUID) -> None:
        """
        Removes given file member from a file.

        Raises:
            File.ActionNotAllowed: If removing a file member is not allowed.
            File.NotFound: If file with a given ID does not exist.
            Namespace.NotFound: If namespace with a target path does not exist.
        """
        file = await self.file.get_by_id(ns_path, file_id)
        namespace = await self.namespace.get_by_path(ns_path)
        if not file.can_reshare() and namespace.owner_id != user_id:
            raise File.ActionNotAllowed()
        await self.file_member.remove(file.id, user_id)

    async def revoke_link(self, token: str) -> None:
        await self.sharing.revoke_link(token)

    async def set_member_actions(
        self, ns_path: str, file_id: UUID, user_id: UUID, actions: FileMemberActions
    ) -> None:
        """
        Set available actions for a file member of a file.

        Raises:
            File.ActionNotAllowed: If setting actions for a file member is not allowed.
            File.NotFound: If file with a given ID does not exist.
        """
        file = await self.file.get_by_id(ns_path, file_id)
        if not file.can_reshare():
            raise File.ActionNotAllowed()
        await self.file_member.set_actions(file.id, user_id, actions=actions)
