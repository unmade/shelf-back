from __future__ import annotations

import contextlib
import itertools
from collections import deque
from typing import TYPE_CHECKING

from app.app.files.domain import File, Path, mediatypes
from app.app.files.repositories.file import FileUpdate
from app.app.infrastructure.database import SENTINEL_ID
from app.cache import disk_cache
from app.toolkit import taskgroups

from . import thumbnails

if TYPE_CHECKING:
    from typing import (
        IO,
        AsyncIterator,
        Iterable,
        Protocol,
        Sequence,
    )

    from app.app.files.domain import AnyPath
    from app.app.files.repositories import IFileRepository
    from app.app.infrastructure import IDatabase
    from app.app.infrastructure.storage import ContentReader, IStorage
    from app.typedefs import StrOrUUID

    class IServiceDatabase(IDatabase, Protocol):
        file: IFileRepository

__all__ = ["FileCoreService"]


def _make_thumbnail_ttl(*args, size: int, **kwargs) -> str:
    if size < 128:
        return "7d"
    return "24h"


class FileCoreService:
    """A service with primitives for storing and retrieving files."""

    __slots__ = ["db", "storage"]

    def __init__(self, database: IServiceDatabase, storage: IStorage):
        self.db = database
        self.storage = storage

    async def create_file(
        self, ns_path: AnyPath, path: AnyPath, content: IO[bytes]
    ) -> File:
        path = Path(path)
        try:
            parent = await self.db.file.get_by_path(ns_path, path.parent)
        except File.NotFound:
            await self.create_folder(ns_path, str(path.parent))
        else:
            if not parent.is_folder():
                raise File.NotADirectory()

        next_path = await self.get_available_path(ns_path, path)
        mediatype = mediatypes.guess(content, name=path.name)

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
        Creates a folder with any missing parents in a namespace with a `ns_path`.

        Args:
            ns_path (Namespace): Namespace path where a folder should be created.
            path (AnyPath): Path to a folder to create.

        Raises:
            File.NotADirectory: If one of the path parents is not a directory.

        Returns:
            File: Created folder.
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

        Args:
            ns_path (AnyPath): Namespace path where file/folder should be deleted.
            path (AnyPath): Path to a file/folder to delete.

        Raises:
            File.NotFound: If a file/folder with a given path does not exists.

        Returns:
            File: Deleted file.
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

    async def download(self, file_id: StrOrUUID) -> ContentReader:
        file = await self.get_by_id(str(file_id))
        if file.is_folder():
            download_func = self.storage.downloaddir
        else:
            download_func = self.storage.download
        return await download_func(file.ns_path, file.path)

    async def empty_folder(self, ns_path: AnyPath, path: AnyPath) -> None:
        file = await self.db.file.get_by_path(ns_path, path)
        if file.size == 0:
            return

        paths = [*file.path.parents, path]
        async for _ in self.db.atomic():
            await self.db.file.delete_all_with_prefix(ns_path, f"{path}/")
            await self.db.file.incr_size_batch(ns_path, paths, value=-file.size)
        await self.storage.emptydir(ns_path, path)

    async def exists_with_id(self, ns_path: AnyPath, file_id: StrOrUUID) -> bool:
        return await self.db.file.exists_with_id(ns_path, file_id)

    async def exists_at_path(self, ns_path: AnyPath, path: AnyPath) -> bool:
        return await self.db.file.exists_at_path(ns_path, path)

    async def get_available_path(self, ns_path: AnyPath, path: AnyPath) -> Path:
        """
        Returns a path with modified name if the current one is already taken, otherwise
        returns path unchanged.

        For example, if path 'a/f.tar.gz' exists, then the next path will be as follows
        'a/f (1).tar.gz'.

        Args:
            ns_path (AnyPath): Namespace path where to look for a path.
            path (AnyPath): Target path.

        Returns:
            Path: an available file path
        """
        path = Path(path)
        if not await self.db.file.exists_at_path(ns_path, path):
            return path

        pattern = f"{path.stem} \\([[:digit:]]+\\){path.suffix}"
        count = await self.db.file.count_by_path_pattern(ns_path, pattern)
        return path.with_stem(f"{path.stem} ({count + 1})")

    async def get_by_id(self, file_id: str) -> File:
        """
        Return a file by ID.

        Args:
            file_id (StrOrUUID): File ID.

        Raises:
            File.NotFound: If file with a given ID does not exists.

        Returns:
            File: File with a target ID.
        """
        return await self.db.file.get_by_id(file_id)

    async def get_by_id_batch(
        self, ns_path: AnyPath, ids: Iterable[StrOrUUID]
    ) -> list[File]:
        """
        Returns all files with target IDs.

        Args:
            ns_path (AnyPath): Namespace where files are located.
            ids (Iterable[StrOrUUID]): Iterable of paths to look for.

        Returns:
            List[File]: Files with target IDs.
        """
        return await self.db.file.get_by_id_batch(ns_path, ids)

    async def get_by_path(self, ns_path: AnyPath, path: AnyPath) -> File:
        """
        Return a file at a target path.

        Args:
            ns_path (AnyPath): Namespace path where a file is located.
            path (AnyPath): Path to a file.

        Raises:
            File.NotFound: If a file with a target path does not exists.

        Returns:
            File: File with at a target path.
        """
        return await self.db.file.get_by_path(ns_path, path)

    async def iter_by_mediatypes(
        self,
        ns_path: AnyPath,
        mediatypes: Sequence[str],
        *,
        batch_size: int = 25,
    ) -> AsyncIterator[list[File]]:
        """
        Iterates through all files of a given mediatypes in batches.

        Args:
            ns_path (AnyPath): Target namespace where files should be listed.
            mediatypes (Iterable[str]): List of mediatypes that files should match.
            batch_size (int, optional): Batch size. Defaults to 25.

        Returns:
            AsyncIterator[list[File]]: None.

        Yields:
            Iterator[AsyncIterator[list[File]]]: Batch with files with a given
                mediatypes.
        """
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

    async def list_folder(self, ns_path: AnyPath, path: AnyPath) -> list[File]:
        """
        Lists all files in the folder at a given path.

        Use "." to list top-level files and folders.

        Args:
            ns_path (AnyPath): Namespace path where a folder located.
            path (AnyPath): Path to a folder in the target namespace.

        Raises:
            File.NotFound: If folder at this path does not exists.
            File.NotADirectory: If path points to a file.

        Returns:
            List[File]: List of all files/folders in a folder with a target path.
        """
        folder = await self.get_by_path(ns_path, path)
        if not folder.is_folder():
            raise File.NotADirectory()

        prefix = "" if path == "." else f"{path}/"
        return await self.db.file.list_with_prefix(ns_path, prefix)

    async def move(
        self, ns_path: AnyPath, at_path: AnyPath, to_path: AnyPath
    ) -> File:
        """
        Moves a file or a folder to a different location in the target Namespace.
        If the source path is a folder all its contents will be moved.

        Args:
            ns_path (AnyPath): Namespace path where file/folder should be moved
            at_path (AnyPath): Path to be moved.
            to_path (AnyPath): Path that is the destination.

        Raises:
            File.NotFound: If source path does not exists.
            File.AlreadyExists: If some file already in the destination path.
            File.MissingParent: If 'next_path' parent does not exists.
            File.NotADirectory: If one of the 'next_path' parents is not a folder.

        Returns:
            File: Moved file/folder.
        """
        at_path = Path(at_path)
        to_path = Path(to_path)

        renamed = at_path == to_path and str(at_path) != str(to_path)
        assert not to_path.is_relative_to(at_path) or renamed, (
            "Can't move to itself."
        )

        paths = [at_path, to_path, to_path.parent]
        files = {
            file.path: file
            for file in await self.db.file.get_by_path_batch(ns_path, paths)
        }

        file = files.get(at_path)
        if file is None:
            raise File.NotFound() from None

        if to_path.parent not in files:
            raise File.MissingParent() from None

        next_parent = files[to_path.parent]
        if not next_parent.is_folder():
            raise File.NotADirectory() from None

        if at_path != to_path:
            if to_path in files:
                raise File.AlreadyExists() from None

        # preserve parent casing
        to_path = next_parent.path / to_path.name
        return await self._move(file, to_path)

    async def _move(self, file: File, next_path: AnyPath) -> File:
        """Actually moves a file or a folder in the storage and in the database."""
        ns_path = file.ns_path
        path = file.path
        next_path = Path(next_path)

        to_decrease = set(path.parents) - set(next_path.parents)
        to_increase = set(next_path.parents) - set(path.parents)

        file_update = FileUpdate(
            id=file.id,
            name=next_path.name,
            path=str(next_path),
        )

        move_storage = self.storage.movedir if file.is_folder() else self.storage.move
        await move_storage(ns_path, file.path, file_update["path"])
        async for _ in self.db.atomic():
            updated_file = await self.db.file.update(file_update)
            if file.is_folder():
                await self.db.file.replace_path_prefix(ns_path, path, next_path)
            await self.db.file.incr_size_batch(ns_path, to_decrease, value=-file.size)
            await self.db.file.incr_size_batch(ns_path, to_increase, value=file.size)
        return updated_file

    async def reindex(self, ns_path: AnyPath, path: AnyPath) -> None:
        """
        Creates files that are missing in the database, but present in the storage and
        removes files that are present in the database, but missing in the storage
        at a given path.

        The method doesn't guarantee to accurately re-calculate path parents sizes.

        Args:
            ns_path (AnyPath): Namespace path where files will be reindexed.
            path (AnyPath): Path to a folder that should be reindexed.

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
            for file in await self.storage.iterdir(ns_path, folder):
                if file.is_dir():
                    folders.append(Path(file.path))
                    size = 0
                    mediatype = mediatypes.FOLDER
                else:
                    if (key := folder) in missing:
                        missing[key].size += file.size
                    total_size += file.size
                    size = file.size
                    mediatype = mediatypes.guess_unsafe(file.name)

                missing[Path(file.path)] = File(
                    id=SENTINEL_ID,
                    ns_path=ns_path,
                    name=file.name,
                    path=file.path,
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

        file_update = FileUpdate(id=root.id, size=total_size)
        await self.db.file.update(file_update)

    @disk_cache(key="{file_id}:{size}", ttl=_make_thumbnail_ttl)
    async def thumbnail(self, file_id: str, *, size: int) -> tuple[File, bytes]:
        """
        Generate in-memory thumbnail with preserved aspect ratio.

        Args:
            file_id (StrOrUUID): Target file ID.
            size (int): Thumbnail dimension.

        Raises:
            File.NotFound: If file with this path does not exists.
            File.IsADirectory: If file is a directory.
            ThumbnailUnavailable: If file is not an image.

        Returns:
            tuple[File, bytes]: Tuple of file and thumbnail content.
        """
        file = await self.db.file.get_by_id(file_id)
        content_reader = await self.storage.download(file.ns_path, file.path)
        content = await content_reader.stream()
        thumbnail = await thumbnails.thumbnail(content, size=size)
        return file, thumbnail
