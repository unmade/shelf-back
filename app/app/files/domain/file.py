from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.toolkit import timezone
from app.toolkit.mediatypes import MediaType

from .path import Path

__all__ = ["File"]


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


class MalformedPath(FileError):
    pass


class MissingParent(FileError):
    pass


class NotADirectory(FileError):
    pass


class ThumbnailUnavailable(FileError):
    pass


class File(BaseModel):
    Error: ClassVar[type[Exception]] = FileError
    ActionNotAllowed: ClassVar[type[FileActionNotAllowed]] = FileActionNotAllowed
    AlreadyExists: ClassVar[type[FileAlreadyExists]] = FileAlreadyExists
    NotFound: ClassVar[type[FileNotFound]] = FileNotFound
    TooLarge: ClassVar[type[FileTooLarge]] = FileTooLarge
    IsADirectory: ClassVar[type[IsADirectory]] = IsADirectory
    MalformedPath: ClassVar[type[MalformedPath]] = MalformedPath
    MissingParent: ClassVar[type[MissingParent]] = MissingParent
    NotADirectory: ClassVar[type[NotADirectory]] = NotADirectory
    ThumbnailUnavailable: ClassVar[type[ThumbnailUnavailable]] = ThumbnailUnavailable

    id: UUID
    blob_id: UUID | None = None
    owner_id: UUID
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
        return self.mediatype == MediaType.FOLDER

    def is_hidden(self) -> bool:
        """True if file name startswith '.', False othewise."""
        return self.name.startswith(".")
