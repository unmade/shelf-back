from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.app.files.domain import FileMember

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.files.repositories.file_member import IFileMemberRepository

    class IServiceDatabase(Protocol):
        file_member: IFileMemberRepository

__all__ = ["FileMemberService"]


class FileMemberService:
    __slots__ = ("db", )

    def __init__(self, database: IServiceDatabase) -> None:
        self.db = database

    async def add(self, file_id: str, user_id: UUID) -> FileMember:
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
                user=FileMember.User(
                    id=user_id,
                    username="",
                ),
            )
        )

    async def list_all(self, file_id: str) -> list[FileMember]:
        """List all file members for a file with a given ID."""
        return await self.db.file_member.list_all(file_id)
