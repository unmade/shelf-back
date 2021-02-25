from __future__ import annotations

import os
import shutil
from os.path import join
from pathlib import Path
from typing import IO, TYPE_CHECKING, Generator, Iterator, Type, TypeVar

import zipfly

from app import config, errors

if TYPE_CHECKING:
    from app.typedefs import StrOrPath

T = TypeVar("T", bound="StorageFile")


class StorageFile:
    __slots__ = ("name", "path", "size", "mtime", "is_dir")

    def __init__(self, name: str, path: Path, size: int, mtime: float, is_dir: bool):
        self.name = name
        self.path = path
        self.size = size
        self.mtime = mtime
        self.is_dir = is_dir

    @classmethod
    def from_path(cls: Type[T], path: StrOrPath, rel_to: StrOrPath) -> T:
        path = Path(path)
        stat = path.lstat()
        return cls(
            name=path.name,
            path=path.relative_to(rel_to),
            size=stat.st_size,
            mtime=stat.st_mtime,
            is_dir=path.is_dir(),
        )

    def __str__(self) -> str:
        return str(self.path)


class LocalStorage:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir

    def iterdir(self, path: StrOrPath) -> Iterator[StorageFile]:
        dir_path = self.root_dir / path
        try:
            return (
                StorageFile.from_path(file, self.root_dir)
                for file in dir_path.iterdir()
            )
        except NotADirectoryError as exc:
            raise errors.NotADirectory() from exc

    def save(self, path: StrOrPath, file: IO[bytes]) -> StorageFile:
        file.seek(0)
        fullpath = self.root_dir / path
        with fullpath.open("wb") as buffer:
            shutil.copyfileobj(file, buffer)

        return StorageFile.from_path(fullpath, self.root_dir)

    def mkdir(self, path: StrOrPath) -> StorageFile:
        dir_path = self.root_dir / path
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
        except NotADirectoryError as exc:
            raise errors.NotADirectory() from exc
        return StorageFile.from_path(dir_path, self.root_dir)

    def get(self, path: StrOrPath) -> StorageFile:
        fullpath = self.root_dir / path
        try:
            return StorageFile.from_path(fullpath, self.root_dir)
        except FileNotFoundError as exc:
            raise errors.FileNotFound() from exc

    def is_exists(self, path: StrOrPath) -> bool:
        fullpath = self.root_dir / path
        return fullpath.exists()

    def is_dir_exists(self, path: StrOrPath) -> bool:
        fullpath = self.root_dir / path
        return fullpath.exists() and fullpath.is_dir()

    def move(self, from_path: StrOrPath, to_path: StrOrPath) -> None:
        shutil.move(self.root_dir / from_path, self.root_dir / to_path)

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
        else:
            paths = [{"fs": str(fullpath), "n": fullpath.name}]

        attachment = zipfly.ZipFly(paths=paths)
        return attachment.generator()  # type: ignore

    def delete(self, path: StrOrPath) -> None:
        fullpath = self.root_dir / path
        if fullpath.is_dir():
            shutil.rmtree(fullpath)
        else:
            fullpath.unlink()

    def delete_dir_content(self, path: StrOrPath) -> None:
        fullpath = self.root_dir / path
        with os.scandir(fullpath) as it:
            for entry in it:
                if entry.is_dir():
                    shutil.rmtree(entry.path)
                else:
                    os.unlink(entry.path)

    def walk(
        self, path: StrOrPath
    ) -> Iterator[tuple[Path, Iterator[StorageFile], Iterator[StorageFile]]]:
        for root, dirs, files in os.walk(self.root_dir / path):
            yield (
                Path(root).relative_to(self.root_dir),
                (StorageFile.from_path(join(root, d), self.root_dir) for d in dirs),
                (StorageFile.from_path(join(root, f), self.root_dir) for f in files),
            )


storage = LocalStorage(config.STATIC_DIR)
