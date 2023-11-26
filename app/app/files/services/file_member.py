from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.app.files.domain import FileMember
from app.app.files.repositories.file_member import FileMemberUpdate

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.files.domain.file_member import FileMemberActions
    from app.app.files.repositories import IFileMemberRepository
    from app.app.files.services.file import FileCoreService

    class IServiceDatabase(Protocol):
        file_member: IFileMemberRepository

__all__ = ["FileMemberService"]


class FileMemberService:
    __slots__ = ("db", "filecore")

    def __init__(self, database: IServiceDatabase, filecore: FileCoreService) -> None:
        self.db = database
        self.filecore = filecore

    async def add(
        self,
        file_id: UUID,
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

    async def get(self, file_id: UUID, user_id: UUID) -> FileMember:
        """
        Returns a member by user ID of a file with a target ID.

        Raises:
            FileMember.NotFound: If file member does not exist.
        """
        return await self.db.file_member.get(file_id, user_id)

    async def list_all(self, file_id: UUID) -> list[FileMember]:
        """List all file members for a file with a given ID."""
        return await self.db.file_member.list_all(file_id)

    async def list_by_user_id(
        self, user_id: UUID, *, limit: int = 25
    ) -> list[FileMember]:
        """Lists all files shared with a given user including the ones user owns."""
        return await self.db.file_member.list_by_user_id(user_id, limit=limit)

    async def remove(self, file_id: UUID, user_id: UUID) -> None:
        """Removes a file member."""
        await self.db.file_member.delete(file_id, user_id)

    async def set_actions(
        self, file_id: UUID, user_id: UUID, actions: FileMemberActions
    ) -> FileMember:
        """
        Sets file member actions.

        Raises:
            FileMember.NotFound: If file member does not exist.
        """
        member = await self.db.file_member.get(file_id, user_id)
        member_update = FileMemberUpdate(actions=actions)
        return await self.db.file_member.update(member, member_update)
