from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.app.files.domain import mediatypes
from app.toolkit import json_, timezone

if TYPE_CHECKING:
    from app.typedefs import StrOrUUID

__all__ = ["File"]


def mtime_factory() -> float:
    return timezone.now().timestamp()


class FileError(Exception):
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


class File:
    __slots__ = ("id", "ns_path", "name", "path", "size", "mtime", "mediatype")

    Error = FileError
    AlreadyExists = FileAlreadyExists
    NotFound = FileNotFound
    TooLarge = FileTooLarge
    IsADirectory = IsADirectory
    MalformedPath = MalformedPath
    MissingParent = MissingParent
    NotADirectory = NotADirectory
    ThumbnailUnavailable = ThumbnailUnavailable

    def __init__(
        self,
        *,
        id: StrOrUUID,
        ns_path: str,
        name: str,
        path: str,
        size: int,
        mediatype: str,
        mtime: float | None = None,
    ) -> None:
        self.id = str(id)
        self.ns_path = ns_path
        self.name = name
        self.path = path
        self.size = size
        self.mtime = mtime or mtime_factory()
        self.mediatype = mediatype

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, File):
            return NotImplemented

        return all(
            getattr(self, field) == getattr(other, field)
            for field in self.__slots__
        )

    def is_folder(self) -> bool:
        """True if file is a folder, False otherwise."""
        return self.mediatype == mediatypes.FOLDER

    def is_hidden(self) -> bool:
        """True if file name startswith '.', False othewise."""
        return self.name.startswith(".")

    def json(self) -> str:
        """Dump instance to json."""
        return json_.dumps({
            "id": str(self.id),
            "ns_path": self.ns_path,
            "name": self.name,
            "path": self.path,
            "size": self.size,
            "mtime": self.mtime,
            "mediatype": self.mediatype,
        })
