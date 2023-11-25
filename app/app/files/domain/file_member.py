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
    can_delete: bool = False
    can_download: bool = False
    can_move: bool = False
    can_reshare: bool = False
    can_unshare: bool = False
    can_upload: bool = False
    can_view: bool = False


class FileMemberUser(BaseModel):
    id: UUID
    username: str


class FileMember(BaseModel):
    OWNER: ClassVar[FileMemberActions] = FileMemberActions(
        can_delete=True,
        can_download=True,
        can_move=True,
        can_reshare=True,
        can_upload=True,
        can_unshare=True,
        can_view=True,
    )
    EDITOR: ClassVar[FileMemberActions] = FileMemberActions(
        can_delete=True,
        can_download=True,
        can_move=True,
        can_reshare=True,
        can_unshare=False,
        can_upload=True,
        can_view=True,
    )
    VIEWER: ClassVar[FileMemberActions] = FileMemberActions(
        can_delete=False,
        can_download=True,
        can_move=False,
        can_reshare=False,
        can_upload=False,
        can_view=True,
    )

    Actions: ClassVar[type[FileMemberActions]] = FileMemberActions
    User: ClassVar[type[FileMemberUser]] = FileMemberUser

    AlreadyExists: ClassVar[type[Exception]] = FileMemberAlreadyExists
    NotFound: ClassVar[type[Exception]] = FileMemberNotFound

    file_id: UUID
    actions: FileMemberActions
    user: FileMemberUser

    @property
    def display_name(self) -> str:
        return self.user.username

    @property
    def owner(self) -> bool:
        return self.actions == self.OWNER
