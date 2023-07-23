from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.app.files.domain import FileMember

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.files.domain.file_member import FileMemberActions
    from app.app.files.repositories import IFileMemberRepository
    from app.app.files.services.file import FileCoreService
    from app.app.users.repositories import IUserRepository

    class IServiceDatabase(Protocol):
        file_member: IFileMemberRepository
        user: IUserRepository

__all__ = ["FileMemberService"]


class FileMemberService:
    __slots__ = ("db", "filecore")

    def __init__(self, database: IServiceDatabase, filecore: FileCoreService) -> None:
        self.db = database
        self.filecore = filecore

    async def add(
        self,
        file_id: str,
        user_id: UUID,
        actions: FileMemberActions,
    ) -> FileMember:
        """
        Creates a new file member.

        Raises:
            File.NotFound: If file with a given ID does not exist.
            FileMember.AlreadyExists: If user already a member of the target file.
            User.NotFound: If user with a given username does not exist.
        """
        file = await self.filecore.get_by_id(file_id)
        user = await self.db.user.get_by_username(file.ns_path)
        if user.id == user_id:
            raise FileMember.AlreadyExists() from None

        return await self.db.file_member.save(
            FileMember(
                file_id=file_id,
                actions=actions,
                user=FileMember.User(
                    id=user_id,
                    username="",  # hack: will be set in the repository
                ),
            )
        )

    async def list_all(self, file_id: str) -> list[FileMember]:
        """
        List all file members for a file with a given ID.

        Raises:
            File.NotFound: If file with a target ID does not exist.
        """
        file = await self.filecore.get_by_id(file_id)
        user = await self.db.user.get_by_username(file.ns_path)
        members = await self.db.file_member.list_all(file_id)
        return [
            FileMember(
                file_id=file_id,
                owner=True,
                actions=FileMember.EDITOR,
                user=FileMember.User(
                    id=user.id,
                    username=user.username,
                ),
            ),
            *members,
        ]

    async def remove(self, file_id: str, user_id: UUID) -> None:
        """Removes a file member."""
        await self.db.file_member.delete(file_id, user_id)
