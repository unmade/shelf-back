from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic.functional_validators import BeforeValidator

from app.app.files.domain import mediatypes
from app.toolkit import timezone

from .mount import MountPoint
from .path import Path

__all__ = ["File", "MountedFile"]


def mtime_factory() -> float:
    return timezone.now().timestamp()


def from_uuid(value):
    if isinstance(value, UUID):
        return str(value)
    return value


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
    ActionNotAllowed: ClassVar[type[Exception]] = FileActionNotAllowed
    AlreadyExists: ClassVar[type[Exception]] = FileAlreadyExists
    NotFound: ClassVar[type[Exception]] = FileNotFound
    TooLarge: ClassVar[type[Exception]] = FileTooLarge
    IsADirectory: ClassVar[type[Exception]] = IsADirectory
    IsMounted: ClassVar[type[Exception]] = IsMounted
    MalformedPath: ClassVar[type[Exception]] = MalformedPath
    MissingParent: ClassVar[type[Exception]] = MissingParent
    NotADirectory: ClassVar[type[Exception]] = NotADirectory
    ThumbnailUnavailable: ClassVar[type[Exception]] = ThumbnailUnavailable

    id: Annotated[str, BeforeValidator(from_uuid)]
    ns_path: str
    name: str
    path: Path
    size: int
    mtime: float = Field(default_factory=mtime_factory)
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

    def can_reshare(self) -> bool:
        return True


class MountedFile(_BaseFile):
    """A file with a path that is a mount point or a location in a mount point."""

    mount_point: MountPoint

    def can_reshare(self) -> bool:
        return self.mount_point.can_reshare()
