from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.app.files.domain import mediatypes
from app.toolkit import timezone

from .mount import MountPoint
from .path import Path

__all__ = ["File", "MountedFile"]


class FileError(Exception):
    pass


class FileActionNotAllowed(FileError):
    pass


class FileAlreadyExists(FileError):
    pass


class FileNotFound(FileError):
    pass


class FileTooLarge(FileError):
    pass


class IsADirectory(FileError):
    pass


class IsMounted(FileError):
    pass


class MalformedPath(FileError):
    pass


class MissingParent(FileError):
    pass


class NotADirectory(FileError):
    pass


class ThumbnailUnavailable(FileError):
    pass


class _BaseFile(BaseModel):
    Error: ClassVar[type[Exception]] = FileError
    ActionNotAllowed: ClassVar[type[FileActionNotAllowed]] = FileActionNotAllowed
    AlreadyExists: ClassVar[type[FileAlreadyExists]] = FileAlreadyExists
    NotFound: ClassVar[type[FileNotFound]] = FileNotFound
    TooLarge: ClassVar[type[FileTooLarge]] = FileTooLarge
    IsADirectory: ClassVar[type[IsADirectory]] = IsADirectory
    IsMounted: ClassVar[type[IsMounted]] = IsMounted
    MalformedPath: ClassVar[type[MalformedPath]] = MalformedPath
    MissingParent: ClassVar[type[MissingParent]] = MissingParent
    NotADirectory: ClassVar[type[NotADirectory]] = NotADirectory
    ThumbnailUnavailable: ClassVar[type[ThumbnailUnavailable]] = ThumbnailUnavailable

    id: UUID
    ns_path: str
    name: str
    path: Path
    chash: str
    size: int
    modified_at: datetime = Field(default_factory=timezone.now)
    mediatype: str
    shared: bool = False

    def is_folder(self) -> bool:
        """True if file is a folder, False otherwise."""
        return self.mediatype == mediatypes.FOLDER

    def is_hidden(self) -> bool:
        """True if file name startswith '.', False othewise."""
        return self.name.startswith(".")


class File(_BaseFile):
    """Regular file with a path pointing to the actual location of the file."""

    def can_download(self) -> bool:
        return True

    def can_reshare(self) -> bool:
        return True


class MountedFile(_BaseFile):
    """A file with a path that is a mount point or a location in a mount point."""

    mount_point: MountPoint

    def can_download(self) -> bool:
        return self.mount_point.can_download()

    def can_reshare(self) -> bool:
        return self.mount_point.can_reshare()
