from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

__all__ = ["FileMember"]


class FileMemberAlreadyExists(Exception):
    """If file member already exists."""


class FileMemberUser(BaseModel):
    id: UUID
    username: str


class FileMember(BaseModel):
    User = FileMemberUser

    AlreadyExists = FileMemberAlreadyExists

    file_id: str
    user: FileMemberUser

    @property
    def display_name(self) -> str:
        return self.user.username
