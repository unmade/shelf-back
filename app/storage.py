from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterator, Union

from app import config


class StorageFile:
    __slots__ = ("_file", "_nspath")

    def __init__(self, file: Path, nspath: str):
        self._file = file
        self._nspath = nspath

    def __str__(self) -> str:
        return self.path

    @property
    def name(self) -> str:
        return self._file.name

    @property
    def path(self) -> str:
        return str(self._file.relative_to(self._nspath))

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

    def ls(self, namespace: str, path: Union[None, str, Path]) -> Iterator[StorageFile]:
        nspath = self.root_dir.joinpath(namespace)
        dirpath = nspath.joinpath(str(path)) if path else nspath
        return (StorageFile(file, nspath) for file in dirpath.iterdir())

    def save(self, namespace: str, path: Union[None, str, Path], file) -> StorageFile:
        nspath = self.root_dir.joinpath(namespace)
        fpath = nspath.joinpath(path) if path else nspath
        with fpath.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return StorageFile(fpath, nspath)


storage = LocalStorage(config.STATIC_DIR)
