from __future__ import annotations

import os
import os.path
import shutil
from io import BytesIO
from pathlib import Path
from typing import IO, TYPE_CHECKING, Generator, Iterator, TypeVar

import zipfly
from asgiref.sync import sync_to_async
from PIL import Image, UnidentifiedImageError

from app import config, errors

if TYPE_CHECKING:
    from app.typedefs import StrOrPath

T = TypeVar("T", bound="StorageFile")


def _readchunks(path: StrOrPath) -> Generator[bytes, None, None]:
    chunk_size = 4096
    with open(path, 'rb') as f:
        has_content = True
        while has_content:
            chunk = f.read(chunk_size)
            has_content = len(chunk) == chunk_size
            yield chunk


class StorageFile:
    __slots__ = ("name", "path", "size", "mtime", "is_dir")

    def __init__(self, name: str, path: str, size: int, mtime: float, is_dir: bool):
        self.name = name
        self.path = path
        self.size = size
        self.mtime = mtime
        self.is_dir = is_dir

    def __str__(self) -> str:
        return str(self.path)


class LocalStorage:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir

    def _from_path(self, path: StrOrPath) -> StorageFile:
        path = Path(path)
        stat = path.lstat()
        return StorageFile(
            name=path.name,
            path=os.path.relpath(path, self.root_dir),
            size=stat.st_size,
            mtime=stat.st_mtime,
            is_dir=path.is_dir(),
        )

    def _from_entry(self, entry: os.DirEntry[str]) -> StorageFile:
        stat = entry.stat()
        return StorageFile(
            name=entry.name,
            path=os.path.relpath(entry.path, self.root_dir),
            size=stat.st_size,
            mtime=stat.st_mtime,
            is_dir=entry.is_dir(),
        )

    @sync_to_async
    def delete(self, path: StrOrPath) -> None:
        fullpath = os.path.join(self.root_dir, path)
        try:
            if os.path.isdir(fullpath):
                shutil.rmtree(fullpath)
            else:
                os.unlink(fullpath)
        except FileNotFoundError as exc:
            raise errors.FileNotFound() from exc

    def download(self, path: StrOrPath) -> Generator[bytes, None, None]:
        fullpath = self.root_dir / path
        if fullpath.is_dir():
            paths = [
                {
                    "fs": str(filepath),
                    "n": filepath.relative_to(fullpath),
                }
                for filepath in fullpath.glob("**/*")
                if filepath.is_file()
            ]
            return zipfly.ZipFly(paths=paths).generator()  # type: ignore

        return _readchunks(fullpath)

    @sync_to_async
    def exists(self, path: StrOrPath) -> bool:
        fullpath = os.path.join(self.root_dir, path)
        return os.path.exists(fullpath)

    @sync_to_async
    def get(self, path: StrOrPath) -> StorageFile:
        fullpath = self.root_dir / path
        try:
            return self._from_path(fullpath)
        except FileNotFoundError as exc:
            raise errors.FileNotFound() from exc

    @sync_to_async
    def iterdir(self, path: StrOrPath) -> Iterator[StorageFile]:
        dir_path = os.path.join(self.root_dir, path)
        try:
            return (self._from_entry(entry) for entry in os.scandir(dir_path))
        except NotADirectoryError as exc:
            raise errors.NotADirectory() from exc

    @sync_to_async
    def mkdir(self, path: StrOrPath) -> StorageFile:
        dir_path = self.root_dir / path
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
        except FileExistsError as exc:
            raise errors.FileAlreadyExists() from exc
        except NotADirectoryError as exc:
            raise errors.NotADirectory() from exc
        return self._from_path(dir_path)

    @sync_to_async
    def move(self, from_path: StrOrPath, to_path: StrOrPath) -> None:
        try:
            shutil.move(self.root_dir / from_path, self.root_dir / to_path)
        except FileNotFoundError as exc:
            raise errors.FileNotFound() from exc
        except NotADirectoryError as exc:
            raise errors.NotADirectory() from exc

    @sync_to_async
    def save(self, path: StrOrPath, file: IO[bytes]) -> StorageFile:
        file.seek(0)
        fullpath = self.root_dir / path

        try:
            with fullpath.open("wb") as buffer:
                shutil.copyfileobj(file, buffer)
        except NotADirectoryError as exc:
            raise errors.NotADirectory() from exc

        return self._from_path(fullpath)

    @sync_to_async
    def thumbnail(self, path: StrOrPath, size: int) -> tuple[int, IO[bytes]]:
        buffer = BytesIO()
        try:
            with Image.open(self.root_dir / path) as im:
                im.thumbnail((size, size))
                im.save(buffer, im.format)
        except IsADirectoryError as exc:
            raise errors.IsADirectory(f"Path '{path}' is a directory") from exc
        except UnidentifiedImageError as exc:
            msg = f"Can't generate thumbnail for a file: '{path}'"
            raise errors.ThumbnailUnavailable(msg) from exc

        size = buffer.seek(0, 2)
        buffer.seek(0)

        return size, buffer

    def walk(
        self, path: StrOrPath
    ) -> Iterator[tuple[Path, Iterator[StorageFile], Iterator[StorageFile]]]:
        for root, dirs, files in os.walk(self.root_dir / path):
            yield (
                Path(root).relative_to(self.root_dir),
                (self._from_path(os.path.join(root, d)) for d in dirs),
                (self._from_path(os.path.join(root, f)) for f in files),
            )


storage = LocalStorage(config.STORAGE_ROOT)
