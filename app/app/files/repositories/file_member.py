from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypedDict

from app.app.files.domain.file_member import FileMemberActions

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.files.domain import FileMember

__all__ = [
    "FileMemberUpdate",
    "IFileMemberRepository",
]


class FileMemberUpdate(TypedDict):
    actions: FileMemberActions


class IFileMemberRepository(Protocol):
    async def delete(self, file_id: UUID, user_id: UUID) -> None:
        """Deletes a file member."""

    async def get(self, file_id: UUID, user_id: UUID) -> FileMember:
        """
        Returns a member by user ID of a file with a target ID.

        Raises:
            FileMember.NotFound: If file member does not exist.
        """

    async def list_all(self, file_id: UUID) -> list[FileMember]:
        """Returns a list of all file members for a file with a given ID."""

    async def save(self, entity: FileMember) -> FileMember:
        """
        Saves a new file member to the database.

        Raises:
            File.NotFound: If file with a given ID does not exist.
            FileMember.AlreadyExists: If user already a member of the target file.
            User.NotFound: If user with a given username does not exist.
        """

    async def update(self, entity: FileMember, fields: FileMemberUpdate) -> FileMember:
        """
        Updates a member of a file.

        Raises:
            FileMember.NotFound: If file member does not exist.
        """
