from __future__ import annotations

import os
import pathlib
import shutil
from pathlib import Path
from typing import Generator, Iterator, Union

import zipfly

from app import config


class NotADirectory(Exception):
    pass


class StorageFile:
    __slots__ = ("_file", "_rel_to")

    def __init__(self, file: Path, rel_to: Union[str, Path]):
        self._file = file
        self._rel_to = rel_to

    def __str__(self) -> str:
        return self.path

    @property
    def name(self) -> str:
        return self._file.name

    @property
    def path(self) -> Path:
        return self._file.relative_to(self._rel_to)

    @property
    def size(self) -> int:
        return self._file.lstat().st_size

    @property
    def mtime(self) -> float:
        return self._file.lstat().st_mtime

    def is_dir(self) -> bool:
        return self._file.is_dir()


class LocalStorage:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir

    def iterdir(self, path: Union[str, Path]) -> Iterator[StorageFile]:
        dir_path = self.root_dir.joinpath(path)
        try:
            return (StorageFile(file, self.root_dir) for file in dir_path.iterdir())
        except pathlib.NotADirectoryError as exc:
            raise NotADirectory() from exc

    def save(self, path: Union[str, Path], file) -> StorageFile:
        fpath = self.root_dir.joinpath(path)
        with fpath.open("wb") as buffer:
            shutil.copyfileobj(file, buffer)

        return StorageFile(fpath, self.root_dir)

    def mkdir(self, path: Union[str, Path]) -> StorageFile:
        dir_path = self.root_dir.joinpath(path)
        dir_path.mkdir(parents=True, exist_ok=True)
        return StorageFile(dir_path, self.root_dir)

    def get(self, path: Union[str, Path]) -> StorageFile:
        fullpath = self.root_dir.joinpath(path)
        return StorageFile(fullpath, self.root_dir)

    def is_exists(self, path: Union[str, Path]) -> bool:
        fullpath = self.root_dir.joinpath(path)
        return fullpath.exists()

    def is_dir_exists(self, path: Union[str, Path]) -> bool:
        fullpath = self.root_dir.joinpath(path)
        return fullpath.exists() and fullpath.is_dir()

    def move(self, from_path: Union[str, Path], to_path: Union[str, Path]) -> None:
        shutil.move(self.root_dir.joinpath(from_path), self.root_dir.joinpath(to_path))

    def download(self, path: Union[str, Path]) -> Generator:
        fullpath = self.root_dir.joinpath(path)
        if fullpath.is_dir():
            paths = [
                {"fs": str(filepath), "n": filepath.relative_to(fullpath)}
                for filepath in fullpath.glob("**/*")
                if filepath.is_file()
            ]
        else:
            paths = [{"fs": str(fullpath), "n": fullpath.name}]

        attachment = zipfly.ZipFly(paths=paths)
        return attachment.generator()

    def delete(self, path: Union[str, Path]) -> None:
        fullpath = self.root_dir.joinpath(path)
        if fullpath.is_dir():
            shutil.rmtree(fullpath)
        else:
            fullpath.unlink()

    def delete_dir_content(self, path: Union[str, Path]) -> None:
        fullpath = self.root_dir.joinpath(path)
        with os.scandir(fullpath) as it:
            for entry in it:
                if entry.is_dir():
                    shutil.rmtree(entry.path)
                else:
                    os.unlink(entry.path)


storage = LocalStorage(config.STATIC_DIR)
