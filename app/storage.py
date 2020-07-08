from __future__ import annotations

import pathlib
import shutil
from pathlib import Path
from typing import Iterator, Union

from app import config


class NotADirectory(Exception):
    pass


class StorageFile:
    __slots__ = ("_file", "_rel_to")

    def __init__(self, file: Path, rel_to: str):
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


storage = LocalStorage(config.STATIC_DIR)
