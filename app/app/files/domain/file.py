from __future__ import annotations

from typing import TYPE_CHECKING, Any

import orjson

from app import mediatypes, timezone
from app.errors import Error, ErrorCode

if TYPE_CHECKING:
    from app.typedefs import StrOrUUID

__all__ = ["File"]


def mtime_factory() -> float:
    return timezone.now().timestamp()


def orjson_dumps(value, *, default=None) -> str:
    # orjson.dumps returns bytes, to match standard json.dumps we need to decode
    return orjson.dumps(value, default=default).decode()


class FileAlreadyExists(Error):
    code = ErrorCode.file_already_exists


class FileNotFound(Error):
    code = ErrorCode.file_not_found


class FileTooLarge(Error):
    code = ErrorCode.file_too_large


class IsADirectory(Error):
    code = ErrorCode.is_a_directory


class MalformedPath(Error):
    code = ErrorCode.malformed_path


class MissingParent(Error):
    code = ErrorCode.missing_parent


class NotADirectory(Error):
    code = ErrorCode.not_a_directory


class File:
    __slots__ = ("id", "ns_path", "name", "path", "size", "mtime", "mediatype")

    AlreadyExists = FileAlreadyExists
    NotFound = FileNotFound
    TooLarge = FileTooLarge
    IsADirectory = IsADirectory
    MalformedPath = MalformedPath
    MissingParent = MissingParent
    NotADirectory = NotADirectory

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
        return orjson_dumps({
            "id": str(self.id),
            "ns_path": self.ns_path,
            "name": self.name,
            "path": self.path,
            "size": self.size,
            "mtime": self.mtime,
            "mediatype": self.mediatype,
        })
