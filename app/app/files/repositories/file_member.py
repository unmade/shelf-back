from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.app.files.domain import FileMember

__all__ = ["IFileMemberRepository"]


class IFileMemberRepository(Protocol):
    async def list_all(self, file_id: str) -> list[FileMember]:
        """Returns a list of all file members for a file with a given ID."""

    async def save(self, entity: FileMember) -> FileMember:
        """
        Saves a new file member to the database.

        Raises:
            File.NotFound: If file with a given ID does not exist.
            FileMember.AlreadyExists: If user already a member of the target file.
            User.NotFound: If user with a given username does not exist.
        """
