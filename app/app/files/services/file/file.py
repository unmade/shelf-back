from __future__ import annotations

from typing import IO, TYPE_CHECKING

from app.app.files.domain import File, MountedFile, MountPoint, Path
from app.cache import disk_cache
from app.toolkit import taskgroups

from . import thumbnails

if TYPE_CHECKING:
    from collections.abc import Iterable

    from app.app.files.domain import AnyFile, AnyPath
    from app.app.files.services.file import FileCoreService, MountService
    from app.app.infrastructure.storage import ContentReader
    from app.typedefs import StrOrUUID


def _make_thumbnail_ttl(*args, size: int, **kwargs) -> str:
    if size < 128:
        return "7d"
    return "24h"


def _resolve_file(file: AnyFile, mount_point: MountPoint | None) -> AnyFile:
    """Resolves a file to regular or mounted file based on a provided mount point."""
    if mount_point is None:
        return file

    if isinstance(file, MountedFile):
        return file

    relpath = str(file.path)[len(str(mount_point.source.path)) + 1:]
    path = mount_point.display_path / relpath

    return MountedFile(
        id=file.id,
        ns_path=mount_point.folder.ns_path,
        name=path.name,
        path=path,
        size=file.size,
        mtime=file.mtime,
        mediatype=file.mediatype,
        mount_point=mount_point,
    )


class FileService:
    """
    A service to manipulate regular and mounted files.

    The service operates with a real file path as well as mounted ones. If path is a
    mounted path (points to a mount point or inside mount point), then it is resolved
    relative to a target namespace.
    """

    __slots__ = ["filecore", "mount_service"]

    def __init__(self, filecore: FileCoreService, mount_service: MountService):
        self.filecore = filecore
        self.mount_service = mount_service

    async def create_file(
        self, ns_path: AnyPath, path: AnyPath, content: IO[bytes]
    ) -> AnyFile:
        """
        Creates a new file with any missing parents. If file name is taken, then file
        automatically renamed to a next available name.

        Raises:
            File.AlreadyExists: If a file in a target path already exists.
            File.NotADirectory: If one of the path parents is not a folder.
        """
        fq_path = await self.mount_service.resolve_path(ns_path, path)
        file = await self.filecore.create_file(fq_path.ns_path, fq_path.path, content)
        return _resolve_file(file, fq_path.mount_point)

    async def create_folder(self, ns_path: AnyPath, path: AnyPath) -> AnyFile:
        """
        Creates a folder with any missing parents in a namespace with a `ns_path`.

        Raises:
            File.AlreadyExists: If folder with this path already exists.
            File.NotADirectory: If one of the path parents is not a directory.
        """
        fq_path = await self.mount_service.resolve_path(ns_path, path)
        file = await self.filecore.create_folder(fq_path.ns_path, fq_path.path)
        return _resolve_file(file, fq_path.mount_point)

    async def delete(self, ns_path: AnyPath, path: AnyPath) -> AnyFile:
        """
        Permanently deletes a file. If path is a folder deletes a folder with all of its
        contents.

        Raises:
            File.NotFound: If a file/folder with a given path does not exist.
        """
        fq_path = await self.mount_service.resolve_path(ns_path, path)
        if fq_path.is_mount_point():
            raise File.NotFound()
        file = await self.filecore.delete(fq_path.ns_path, fq_path.path)
        return _resolve_file(file, fq_path.mount_point)

    async def download(
        self, ns_path: AnyPath, path: AnyPath
    ) -> tuple[AnyFile, ContentReader]:
        """
        Downloads a file or a folder at a given path.

        Raises:
            File.NotFound: If a file at a target path does not exist.
        """
        fq_path = await self.mount_service.resolve_path(ns_path, path)
        file = await self.filecore.get_by_path(fq_path.ns_path, fq_path.path)
        _, content = await self.filecore.download(file.id)
        return _resolve_file(file, fq_path.mount_point), content

    async def empty_folder(self, ns_path: AnyPath, path: AnyPath) -> None:
        """
        Delete all files and folder at a given folder.

        Raises:
            File.NotFound: If a file at a target path does not exist.
        """
        fq_path = await self.mount_service.resolve_path(ns_path, path)
        await self.filecore.empty_folder(fq_path.ns_path, fq_path.path)

    async def exists_at_path(self, ns_path: AnyPath, path: AnyPath) -> bool:
        """Returns True if file exists at a given path, False otherwise"""
        fq_path = await self.mount_service.resolve_path(ns_path, path)
        return await self.filecore.exists_at_path(fq_path.ns_path, fq_path.path)

    async def get_at_path(self, ns_path: AnyPath, path: AnyPath) -> AnyFile:
        """
        Returns a file at a given path.

        Raises:
            File.NotFound: If file with at a given path does not exist.
        """
        fq_path = await self.mount_service.resolve_path(ns_path, path)
        file = await self.filecore.get_by_path(fq_path.ns_path, fq_path.path)
        return _resolve_file(file, fq_path.mount_point)

    async def get_available_path(self, ns_path: AnyPath, path: AnyPath) -> Path:
        """
        Returns a modified path if the current one is already taken either by a
        mount point or by a regular path, otherwise returns mounted path unchanged.

        For example, if path 'a/f.tar.gz' exists, then the next path will be as follows
        'a/f (1).tar.gz'.
        """
        paths: list[Path] = await taskgroups.gather(
            self.filecore.get_available_path(ns_path, path),
            self.mount_service.get_available_path(ns_path, path),
        )
        if paths[0] == path:
            return paths[1]
        if paths[1] == path:
            return paths[0]
        return max(paths)

    async def get_by_id(self, ns_path: AnyPath, file_id: str) -> AnyFile:
        """
        Returns a file by ID.

        Raises:
            File.NotFound: If file with a given ID does not exist.
        """
        file = await self.filecore.get_by_id(file_id)
        mount_point = None
        if file.ns_path != ns_path:
            mount_point = await self.mount_service.get_closest_by_source(
                file.ns_path, file.path, target_ns_path=str(ns_path)
            )
            if mount_point is None:
                raise File.NotFound()
        return _resolve_file(file, mount_point)

    async def get_by_id_batch(
        self, ns_path: AnyPath, ids: Iterable[StrOrUUID]
    ) -> list[AnyFile]:
        """
        Returns files by ID in the target namespace, including shared files and files
        within shared folders.
        """
        files = await self.filecore.get_by_id_batch(ids)

        fq_paths_map = await self.mount_service.reverse_path_batch(
            ns_path,
            sources=[
                (file.ns_path, file.path)
                for file in files
                if file.ns_path != ns_path
            ],
        )
        mps_map = {
            source: fq_path.mount_point
            for source, fq_path in fq_paths_map.items()
        }

        return [
            _resolve_file(file, mps_map.get((file.ns_path, file.path)))
            for file in files
        ]

    async def list_folder(self, ns_path: AnyPath, path: AnyPath) -> list[AnyFile]:
        """
        Lists all files in the folder at a given path. Use "." to list top-level files
        and folders.

        Raises:
            File.NotFound: If folder at this path does not exists.
            File.NotADirectory: If path points to a file.
        """
        fq_path = await self.mount_service.resolve_path(ns_path, path)
        files = await self.filecore.list_folder(fq_path.ns_path, fq_path.path)
        return [_resolve_file(file, fq_path.mount_point) for file in files]

    async def mount(self, file_id: str, at_folder: tuple[str, AnyPath]) -> None:
        """
        Mounts a file with a given ID to a target folder. The folder must be in a
        different namespace than a file.

        Raises:
            File.IsMounted: If the target folder is a mounted one.
            File.MalformedPath: If file and target folder are in the same namespace.
            File.MissingParent: If folder does not exists.
        """
        ns_path, path = at_folder

        fq_path = await self.mount_service.resolve_path(ns_path, path)
        if fq_path.mount_point is not None:
            raise File.IsMounted()

        if not await self.filecore.exists_at_path(fq_path.ns_path, fq_path.path):
            raise File.MissingParent()

        file = await self.filecore.get_by_id(file_id)
        if file.ns_path == ns_path:
            raise File.MalformedPath()

        mount_path = await self.get_available_path(ns_path, Path(path) / file.name)
        await self.mount_service.create(
            source=(file.ns_path, file.path),
            at_folder=(ns_path, path),
            name=mount_path.name,
        )

    async def move(
        self, ns_path: AnyPath, at_path: AnyPath, to_path: AnyPath
    ) -> AnyFile:
        """
        Moves a file or a folder to a different location in the target Namespace.
        If the source path is a folder all its contents will be moved.

        If a file is moved to the mounted folder then it is actually transferred to
        other namespace - the actual namespace of a mount point.

        Raises:
            File.AlreadyExists: If some file already in the destination path.
            File.MalformedPath: If `at_path` or `to_path` is invalid.
            File.MissingParent: If 'next_path' parent does not exists.
            File.NotFound: If source path does not exists.
            File.NotADirectory: If one of the 'next_path' parents is not a folder.
        """
        at_fq_path = await self.mount_service.resolve_path(ns_path, at_path)
        to_fq_path = await self.mount_service.resolve_path(ns_path, to_path)

        if at_fq_path.mount_point and to_fq_path.mount_point:
            if at_fq_path.mount_point != to_fq_path.mount_point:
                raise File.MalformedPath("Can't move between different mount points.")

        # move mount point
        moved = at_fq_path.is_mount_point() and to_fq_path.is_mount_point()
        renamed = at_fq_path.is_mount_point() and to_fq_path.mount_point is None
        if moved or renamed:
            if await self.filecore.exists_at_path(to_fq_path.ns_path, to_fq_path.path):
                raise File.AlreadyExists()
            mp = await self.mount_service.move(ns_path, at_path, to_path)
            file = await self.filecore.get_by_path(mp.source.ns_path, mp.source.path)
            return _resolve_file(file, mp)

        file = await self.filecore.move(
            at=(at_fq_path.ns_path, at_fq_path.path),
            to=(to_fq_path.ns_path, to_fq_path.path),
        )
        return _resolve_file(file, to_fq_path.mount_point)

    async def reindex(self, ns_path: AnyPath, path: AnyPath) -> None:
        """
        Creates files that are missing in the database, but present in the storage and
        removes files that are present in the database, but missing in the storage
        at a given path.

        Raises:
            File.NotADirectory: If given path does not exist.
        """
        await self.filecore.reindex(ns_path, path)

    @disk_cache(key="{file_id}:{size}", ttl=_make_thumbnail_ttl)
    async def thumbnail(
        self, file_id: str, *, size: int, ns_path: str | None = None
    ) -> tuple[AnyFile, bytes]:
        """
        Generate in-memory thumbnail with preserved aspect ratio.

        If an optional `ns_path` argument is provided, then file ID must exist in that
        namespace.

        Raises:
            File.NotFound: If file with this path does not exists.
            File.IsADirectory: If file is a directory.
            ThumbnailUnavailable: If file is not an image.
        """
        file, content_reader = await self.filecore.download(file_id)
        mount_point = None
        if ns_path and file.ns_path != ns_path:
            mount_point = await self.mount_service.get_closest_by_source(
                file.ns_path, file.path, target_ns_path=ns_path
            )
            if mount_point is None:
                raise File.NotFound() from None

        content = await content_reader.stream()
        thumbnail = await thumbnails.thumbnail(content, size=size)
        return _resolve_file(file, mount_point), thumbnail
