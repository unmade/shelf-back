from __future__ import annotations

import mimetypes
import os.path
from pathlib import PurePath
from typing import Any, Iterator, Self, TypeAlias

__all__ = ["AnyPath", "Path"]


class Path:
    """A case-insenstive path preserving original casing."""

    __slots__ = ["_path"]

    def __init__(self, path: str | Self | PurePath):
        self._path = os.path.normpath(str(path))

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, self.__class__):
            return self._path.lower() == other._path.lower()
        if isinstance(other, str):
            return self._path.lower() == other.lower()
        if isinstance(other, PurePath):
            return self._path.lower() == str(other).lower()
        return NotImplemented

    def __gt__(self, other: Any) -> bool:
        if not isinstance(other, Path):
            return NotImplemented
        return self._path > other._path

    def __ge__(self, other: Any) -> bool:
        if not isinstance(other, Path):
            return NotImplemented
        return self._path >= other._path

    def __hash__(self) -> int:
        return hash((self._path.lower(),))

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, Path):
            return NotImplemented
        return self._path < other._path

    def __le__(self, other: Any) -> bool:
        if not isinstance(other, Path):
            return NotImplemented
        return self._path <= other._path

    def __repr__(self):
        return "{}({!r})".format(self.__class__.__name__, self._path)

    def __rtruediv__(self, key) -> Self:
        if isinstance(key, self.__class__):
            key = str(key)
        try:
            return self.__class__(os.path.join(key, self._path))
        except TypeError:
            return NotImplemented

    def __str__(self) -> str:
        return self._path

    def __truediv__(self, key) -> Self:
        if isinstance(key, Path):
            key = str(key)
        try:
            return self.__class__(os.path.join(self._path, key))
        except TypeError:
            return NotImplemented

    @property
    def name(self) -> str:
        """A string representing the final path component."""
        return os.path.basename(self._path)

    @property
    def parent(self) -> Self:
        """Parent path of this path."""
        return self.__class__(os.path.dirname(self._path))

    @property
    def parents(self) -> Iterator[Self]:
        """An iterator yielding all parents of the path."""
        return (self.__class__(path) for path in PurePath(self._path).parents)

    @property
    def stem(self) -> str:
        """The final path component, without its suffix."""
        return _splitext(self.name)[0]

    @property
    def suffix(self) -> str:
        """The file extension of the final component."""
        return _splitext(self.name)[1]

    def is_relative_to(self, path: AnyPath) -> bool:
        """Returns whether or not this path is relative to the other path."""
        start = os.path.normpath(f"{path}").lower()
        return path == "." or self == path or self._path.lower().startswith(f"{start}/")

    def with_restored_casing(self, path: AnyPath) -> Self:
        if not self.is_relative_to(path):
            raise ValueError("Provided path must be relative to the target path.")
        path = Path(path)
        if str(path) == ".":
            return self
        return self.__class__(f"{path}{self._path[len(str(path)):]}")

    def with_stem(self, next_stem: AnyPath) -> Self:
        """Returns a new path with the stem changed."""
        return self.parent / f"{next_stem}{self.suffix}"


def _splitext(name: str) -> tuple[str, str]:
    encoding = ""
    stem, suffix = os.path.splitext(name)
    if suffix in mimetypes.encodings_map:
        encoding = suffix
        stem, suffix = os.path.splitext(stem)
    return stem, f"{suffix}{encoding}"


AnyPath: TypeAlias = str | PurePath | Path
