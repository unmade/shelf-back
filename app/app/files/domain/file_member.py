from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel

__all__ = [
    "FileMember",
    "FileMemberActions",
]


class FileMemberAlreadyExists(Exception):
    """If file member already exists."""


class FileMemberNotFound(Exception):
    """If file member does not exist."""


class FileMemberActions(BaseModel):
    can_delete: bool
    can_download: bool
    can_move: bool
    can_upload: bool
    can_view: bool


class FileMemberUser(BaseModel):
    id: UUID
    username: str


class FileMember(BaseModel):
    EDITOR: ClassVar[FileMemberActions] = FileMemberActions(
        can_delete=True,
        can_download=True,
        can_move=True,
        can_upload=True,
        can_view=True,
    )
    VIEWER: ClassVar[FileMemberActions] = FileMemberActions(
        can_delete=False,
        can_download=True,
        can_move=False,
        can_upload=False,
        can_view=True,
    )

    Actions = FileMemberActions
    User = FileMemberUser

    AlreadyExists = FileMemberAlreadyExists
    NotFound = FileMemberNotFound

    file_id: str
    owner: bool = False
    actions: FileMemberActions
    user: FileMemberUser

    @property
    def display_name(self) -> str:
        return self.user.username
