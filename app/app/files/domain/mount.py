from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel

from .file_member import FileMemberActions
from .path import Path

__all__ = ["MountPoint"]


class NotFound(Exception):
    """If MountPoint does not exist."""


class _MountPointSource(BaseModel):
    ns_path: str
    path: Path


class _ContainingFolder(BaseModel):
    ns_path: str
    path: Path


class MountPoint(BaseModel):
    Actions: ClassVar[type[FileMemberActions]] = FileMemberActions
    Source: ClassVar[type[_MountPointSource]] = _MountPointSource
    ContainingFolder: ClassVar[type[_ContainingFolder]] = _ContainingFolder

    NotFound: ClassVar[type[Exception]] = NotFound

    source: _MountPointSource
    folder: _ContainingFolder
    display_name: str
    actions: FileMemberActions

    @property
    def display_path(self) -> Path:
        return self.folder.path / self.display_name

    def can_download(self) -> bool:
        return self.actions.can_download

    def can_reshare(self) -> bool:
        return self.actions.can_reshare

    def can_view(self) -> bool:
        return self.actions.can_view
