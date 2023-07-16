from __future__ import annotations

import enum
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel

__all__ = [
    "FileMember",
    "FileMemberAccessLevel",
    "FileMemberPermissions",
]


class FileMemberAlreadyExists(Exception):
    """If file member already exists."""


class FileMemberAccessLevel(str, enum.Enum):
    editor = "editor"
    owner = "owner"
    viewer = "viewer"


class FileMemberPermissions(BaseModel):
    can_delete: bool
    can_download: bool
    can_move: bool
    can_upload: bool
    can_view: bool


class FileMemberUser(BaseModel):
    id: UUID
    username: str


class FileMember(BaseModel):
    EDITOR: ClassVar[FileMemberPermissions] = FileMemberPermissions(
        can_delete=True,
        can_download=True,
        can_move=True,
        can_upload=True,
        can_view=True,
    )

    Permissions = FileMemberPermissions
    AccessLevel = FileMemberAccessLevel
    User = FileMemberUser

    AlreadyExists = FileMemberAlreadyExists

    file_id: str
    access_level: FileMemberAccessLevel
    permissions: FileMemberPermissions
    user: FileMemberUser

    @property
    def display_name(self) -> str:
        return self.user.username
