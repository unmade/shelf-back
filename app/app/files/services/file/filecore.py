from __future__ import annotations

import contextlib
import itertools
from collections import deque
from typing import TYPE_CHECKING

from app.app.files.domain import File, Path, mediatypes
from app.app.files.repositories.file import FileUpdate
from app.app.infrastructure.database import SENTINEL_ID
from app.toolkit import taskgroups

if TYPE_CHECKING:
    from typing import (
        AsyncIterator,
        Iterable,
        Protocol,
        Sequence,
    )
    from uuid import UUID

    from app.app.files.domain import AnyFile, AnyPath, IFileContent
    from app.app.files.repositories import IFileRepository
    from app.app.infrastructure import IDatabase
    from app.app.infrastructure.storage import IStorage

    class IServiceDatabase(IDatabase, Protocol):
        file: IFileRepository

__all__ = ["FileCoreService"]


class FileCoreService:
    """
    A service with file manipulation primitives.

    That service operates only with a real file path.
    """

    __slots__ = ["db", "storage"]

    def __init__(self, database: IServiceDatabase, storage: IStorage):
        self.db = database
        self.storage = storage

    async def create_file(
        self, ns_path: AnyPath, path: AnyPath, content: IFileContent
    ) -> File:
        """
        Saves a file to a storage and to a database. Any missing parents automatically
        created.

        If file name is already taken, then file will be saved under a new name.
        For example - if path 'f.txt' is taken, then new path will be 'f (1).txt'.

        Raises:
            File.AlreadyExists: If a file in a target path already exists.
            File.NotADirectory: If one of the path parents is not a folder.
        """
        path = Path(path)
        try:
            parent = await self.db.file.get_by_path(ns_path, path.parent)
        except File.NotFound:
            await self.create_folder(ns_path, str(path.parent))
        else:
            if not parent.is_folder():
                raise File.NotADirectory()

        next_path = await self.get_available_path(ns_path, path)
        mediatype = mediatypes.guess(content.file, name=path.name)

        storage_file = await self.storage.save(ns_path, next_path, content)

        async for _ in self.db.atomic(attempts=10):
            file = await self.db.file.save(
                File(
                    id=SENTINEL_ID,
                    ns_path=str(ns_path),
                    name=next_path.name,
                    path=next_path,
                    size=storage_file.size,
                    mediatype=mediatype,
                ),
            )
            await self.db.file.incr_size_batch(ns_path, path.parents, file.size)

        return file

    async def create_folder(self, ns_path: AnyPath, path: AnyPath) -> File:
        """
        Creates a folder with any missing parents in a given namespace.

        Raises:
            File.AlreadyExists: If folder with this path already exists.
            File.NotADirectory: If one of the path parents is not a directory.
        """
        path = Path(path)

        paths = list(reversed(list(path.parents))) + [path]
        index = -1

        parents = await self.db.file.get_by_path_batch(ns_path, paths)
        if parents:
            if any(not file.is_folder() for file in parents):
                raise File.NotADirectory()
            if parents[-1].path == path:
                raise File.AlreadyExists()

            index = paths.index(parents[-1].path)
            paths[-1] = path.with_restored_casing(parents[-1].path)

        await self.storage.makedirs(ns_path, path)
        await self.db.file.save_batch(
            [
                File(
                    id=SENTINEL_ID,
                    ns_path=str(ns_path),
                    name=p.name,
                    path=p,
                    size=0,
                    mediatype=mediatypes.FOLDER,
                )
                for p in paths[index+1:]
            ]
        )
        return await self.db.file.get_by_path(ns_path, path)

    async def delete(self, ns_path: AnyPath, path: AnyPath) -> File:
        """
        Permanently deletes a file. If path is a folder deletes a folder with all of its
        contents.

        Raises:
            File.NotFound: If a file/folder with a given path does not exists.
        """
        async for _ in self.db.atomic():
            file = await self.db.file.delete(ns_path, path)
            if file.is_folder():
                await self.db.file.delete_all_with_prefix(ns_path, prefix=f"{path}/")
            parents = file.path.parents
            await self.db.file.incr_size_batch(ns_path, parents, value=-file.size)

        storage = self.storage
        delete_from_storage = storage.deletedir if file.is_folder() else storage.delete
        await delete_from_storage(ns_path, path)

        return file

    async def download(self, file_id: UUID) -> tuple[File, AsyncIterator[bytes]]:
        """
        Downloads a file at a given path.

        Raises:
            File.IsADirectory: If file is a directory.
            File.NotFound: If a file at a target path does not exist.
        """
        file = await self.get_by_id(file_id)
        if file.is_folder():
            raise File.IsADirectory() from None
        return file, self.storage.download(file.ns_path, file.path)

    async def empty_folder(self, ns_path: AnyPath, path: AnyPath) -> None:
        """
        Delete all files and folder at a given folder.

        Raises:
            File.NotFound: If a file at a target path does not exist.
        """
        file = await self.db.file.get_by_path(ns_path, path)
        if file.size == 0:
            return

        paths = [*file.path.parents, path]
        async for _ in self.db.atomic():
            await self.db.file.delete_all_with_prefix(ns_path, f"{path}/")
            await self.db.file.incr_size_batch(ns_path, paths, value=-file.size)
        await self.storage.emptydir(ns_path, path)

    async def exists_with_id(self, ns_path: AnyPath, file_id: UUID) -> bool:
        """Returns True if file exists with a given ID, False otherwise"""
        return await self.db.file.exists_with_id(ns_path, file_id)

    async def exists_at_path(self, ns_path: AnyPath, path: AnyPath) -> bool:
        """Returns True if file exists at a given path, False otherwise"""
        return await self.db.file.exists_at_path(ns_path, path)

    async def get_available_path(self, ns_path: AnyPath, path: AnyPath) -> Path:
        """
        Returns a path with modified name if the current one is already taken, otherwise
        returns path unchanged.

        For example, if path 'a/f.tar.gz' exists, then the next path will be as follows
        'a/f (1).tar.gz'.
        """
        path = Path(path)
        if not await self.db.file.exists_at_path(ns_path, path):
            return path

        pattern = f"{path.stem} \\([[:digit:]]+\\){path.suffix}$"
        count = await self.db.file.count_by_path_pattern(ns_path, pattern)
        return path.with_stem(f"{path.stem} ({count + 1})")

    async def get_by_id(self, file_id: UUID) -> File:
        """
        Return a file by ID.

        Raises:
            File.NotFound: If file with a given ID does not exists.
        """
        return await self.db.file.get_by_id(file_id)

    async def get_by_id_batch(self, ids: Iterable[UUID]) -> list[File]:
        """Returns all files with target IDs."""
        return await self.db.file.get_by_id_batch(ids)

    async def get_by_path(self, ns_path: AnyPath, path: AnyPath) -> File:
        """
        Return a file at a target path.

        Raises:
            File.NotFound: If a file with a target path does not exists.
        """
        return await self.db.file.get_by_path(ns_path, path)

    async def iter_by_mediatypes(
        self,
        ns_path: AnyPath,
        mediatypes: Sequence[str],
        *,
        batch_size: int = 25,
    ) -> AsyncIterator[list[File]]:
        """Iterates through all files of a given mediatypes in batches."""
        limit = batch_size
        offset = -limit

        while True:
            offset += limit
            files = await self.db.file.list_by_mediatypes(
                ns_path, mediatypes, offset=offset, limit=limit
            )
            if not files:
                return
            yield files

    async def list_folder(self, ns_path: AnyPath, path: AnyPath) -> list[AnyFile]:
        """
        Lists all files in the folder at a given path. Use "." to list top-level files
        and folders.

        Raises:
            File.NotFound: If folder at this path does not exists.
            File.NotADirectory: If path points to a file.
        """
        folder = await self.get_by_path(ns_path, path)
        if not folder.is_folder():
            raise File.NotADirectory()

        prefix = "" if path == "." else f"{path}/"
        return await self.db.file.list_with_prefix(ns_path, prefix)

    async def move(
        self, at: tuple[AnyPath, AnyPath], to: tuple[AnyPath, AnyPath]
    ) -> File:
        """
        Moves a file or a folder to a different location in the target namespace.
        If the source path is a folder all its contents will be moved.

        Raises:
            File.AlreadyExists: If some file already in the destination path.
            File.MalformedPath: If `at` or `to` path is invalid.
            File.MissingParent: If 'next_path' parent does not exists.
            File.NotFound: If source path does not exists.
            File.NotADirectory: If one of the 'next_path' parents is not a folder.
        """
        at_ns_path, at_path = at[0], Path(at[1])
        to_ns_path, to_path = to[0], Path(to[1])

        if at_ns_path == to_ns_path:
            case_changed = at_path == to_path and str(at_path) != str(to_path)
            if not case_changed and to_path.is_relative_to(at_path):
                raise File.MalformedPath("Can't move to itself.")

        file = await self.db.file.get_by_path(at_ns_path, at_path)

        paths = [to_path, to_path.parent]
        files = {
            file.path: file
            for file in await self.db.file.get_by_path_batch(to_ns_path, paths)
        }

        next_parent = files.get(to_path.parent)
        if next_parent is None:
            raise File.MissingParent() from None

        if not next_parent.is_folder():
            raise File.NotADirectory() from None

        if at_path != to_path:
            if to_path in files:
                raise File.AlreadyExists() from None

        # preserve parent casing
        to_path = next_parent.path / to_path.name
        return await self._move(file, to_ns_path, to_path)

    async def _move(self, file: File, to_ns_path: AnyPath, to_path: AnyPath) -> File:
        """Actually moves a file or a folder in the storage and in the database."""
        at_ns_path, at_path, size = file.ns_path, file.path, file.size
        to_path = Path(to_path)

        to_decrease = set(at_path.parents)
        to_increase = set(to_path.parents)
        if at_ns_path == to_ns_path:
            to_decrease -= set(to_path.parents)
            to_increase -= set(at_path.parents)

        file_update = FileUpdate(
            ns_path=str(to_ns_path),
            name=to_path.name,
            path=str(to_path),
        )

        move_storage = self.storage.movedir if file.is_folder() else self.storage.move
        await move_storage(at=(at_ns_path, file.path), to=(to_ns_path, to_path))
        async for _ in self.db.atomic():
            updated_file = await self.db.file.update(file, file_update)
            if file.is_folder():
                await self.db.file.replace_path_prefix(
                    at=(at_ns_path, at_path),
                    to=(to_ns_path, to_path),
                )
            await self.db.file.incr_size_batch(at_ns_path, to_decrease, value=-size)
            await self.db.file.incr_size_batch(to_ns_path, to_increase, value=size)
        return updated_file

    async def reindex(self, ns_path: AnyPath, path: AnyPath) -> None:
        """
        Creates files that are missing in the database, but present in the storage and
        removes files that are present in the database, but missing in the storage
        at a given path.

        The method doesn't guarantee to accurately re-calculate path parents sizes.

        Raises:
            File.NotADirectory: If given path does not exist.
        """
        ns_path = str(ns_path)
        # For now, it is faster to re-create all files from scratch
        # than iterating through large directories looking for one missing/dangling file
        prefix = "" if path == "." else f"{path}/"
        await self.db.file.delete_all_with_prefix(ns_path, prefix)

        root = None
        with contextlib.suppress(File.NotFound):
            root = await self.db.file.get_by_path(ns_path, path)
            if root.mediatype != mediatypes.FOLDER:
                raise File.NotADirectory() from None

        missing: dict[Path, File] = {}
        total_size = 0
        folders = deque([Path(path)])
        while len(folders):
            folder = folders.pop()
            async for file in self.storage.iterdir(ns_path, folder):
                if file.is_dir():
                    folders.append(Path(file.path))
                    size = 0
                    mediatype = mediatypes.FOLDER
                else:
                    for item in itertools.chain((folder, ), folder.parents):
                        if item in missing:
                            missing[item].size += file.size
                    total_size += file.size
                    size = file.size
                    mediatype = mediatypes.guess_unsafe(file.name)

                missing[Path(file.path)] = File(
                    id=SENTINEL_ID,
                    ns_path=ns_path,
                    name=file.name,
                    path=file.path,  # type: ignore
                    size=size,
                    mtime=file.mtime,
                    mediatype=mediatype,
                )

        chunk_size = min(len(missing), 500)
        await taskgroups.gather(*(
            self.db.file.save_batch((file for file in chunk if file is not None))
            for chunk in itertools.zip_longest(*[iter(missing.values())] * chunk_size)
        ))

        # creating a folder after `storage.iterdir` do its job in case it fails
        # with `File.NotADirectory` error
        if root is None:
            root = await self.create_folder(ns_path, path)

        file_update = FileUpdate(size=total_size)
        await self.db.file.update(root, file_update)
