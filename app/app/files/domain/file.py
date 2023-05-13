from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any, NamedTuple

from app.app.files.domain import mediatypes
from app.toolkit import json_, timezone

from .mount import MountPoint
from .path import Path

if TYPE_CHECKING:
    from app.typedefs import StrOrUUID

    from .path import AnyPath

__all__ = ["File", "MountedFile", "FullyQualifiedPath"]


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


class _BaseFile:
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
        path: AnyPath,
        size: int,
        mediatype: str,
        mtime: float | None = None,
    ) -> None:
        self.id = str(id)
        self.ns_path = ns_path
        self.name = name
        self.path = Path(path)
        self.size = size
        self.mtime = mtime or mtime_factory()
        self.mediatype = mediatype

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented

        return all(
            getattr(self, field) == getattr(other, field)
            for field in self.__slots__
        )

    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        return f"<{cls_name} ns_path={self.ns_path!r} path={self.path!r}>"

    @property
    @abc.abstractmethod
    def shared(self) -> bool:
        raise NotImplementedError()

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
            "path": str(self.path),
            "size": self.size,
            "mtime": self.mtime,
            "mediatype": self.mediatype,
        })


class File(_BaseFile):
    """Regular file with a path pointing to the actual location of the file."""

    @property
    def shared(self) -> bool:
        return False


class MountedFile(_BaseFile):
    """A file with a path that is a mount point or a location in a mount point."""

    __slots__ = _BaseFile.__slots__ + ("mount_point", )

    def __init__(
        self,
        *,
        id: StrOrUUID,
        ns_path: str,
        name: str,
        path: AnyPath,
        size: int,
        mediatype: str,
        mtime: float | None = None,
        mount_point: MountPoint = None,
    ) -> None:
        super().__init__(
            id=id,
            ns_path=ns_path,
            name=name,
            path=path,
            size=size,
            mediatype=mediatype,
            mtime=mtime,
        )
        self.mount_point = mount_point

    @property
    def shared(self) -> bool:
        return True


class FullyQualifiedPath(NamedTuple):
    """
    A fully qualified path.

    The `ns_path` and `path` always point to the actual location of the file.
    If the `mount_point` is not None than it means the path is mounted.
    """
    ns_path: str
    path: Path
    mount_point: MountPoint | None = None

    def is_mount_point(self) -> bool:
        if self.mount_point is None:
            return False
        return self.mount_point.source.path == self.path
