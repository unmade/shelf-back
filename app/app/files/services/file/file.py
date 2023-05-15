from __future__ import annotations

from typing import IO, TYPE_CHECKING

from app.app.files.domain import File, MountedFile, MountPoint
from app.cache import disk_cache

from . import thumbnails

if TYPE_CHECKING:
    from app.app.files.domain import AnyFile, AnyPath
    from app.app.files.services.file import FileCoreService, MountService
    from app.app.infrastructure.storage import ContentReader


def _make_thumbnail_ttl(*args, size: int, **kwargs) -> str:
    if size < 128:
        return "7d"
    return "24h"


def _resolve_file(file: AnyFile, mount_point: MountPoint | None) -> AnyFile:
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
    __slots__ = ["filecore", "mount_service"]

    def __init__(self, filecore: FileCoreService, mount_service: MountService):
        self.filecore = filecore
        self.mount_service = mount_service

    async def create_file(
        self, ns_path: AnyPath, path: AnyPath, content: IO[bytes]
    ) -> AnyFile:
        fq_path = await self.mount_service.resolve_path(ns_path, path)
        file = await self.filecore.create_file(fq_path.ns_path, fq_path.path, content)
        return _resolve_file(file, fq_path.mount_point)

    async def create_folder(self, ns_path: AnyPath, path: AnyPath) -> AnyFile:
        fq_path = await self.mount_service.resolve_path(ns_path, path)
        file = await self.filecore.create_folder(fq_path.ns_path, fq_path.path)
        return _resolve_file(file, fq_path.mount_point)

    async def delete(self, ns_path: AnyPath, path: AnyPath) -> AnyFile:
        fq_path = await self.mount_service.resolve_path(ns_path, path)
        if fq_path.is_mount_point():
            raise File.NotFound()
        file = await self.filecore.delete(fq_path.ns_path, fq_path.path)
        return _resolve_file(file, fq_path.mount_point)

    async def download(
        self, ns_path: AnyPath, path: AnyPath
    ) -> tuple[AnyFile, ContentReader]:
        fq_path = await self.mount_service.resolve_path(ns_path, path)
        file = await self.filecore.get_by_path(fq_path.ns_path, fq_path.path)
        _, content = await self.filecore.download(file.id)
        return _resolve_file(file, fq_path.mount_point), content

    async def empty_folder(self, ns_path: AnyPath, path: AnyPath) -> None:
        fq_path = await self.mount_service.resolve_path(ns_path, path)
        await self.filecore.empty_folder(fq_path.ns_path, fq_path.path)

    async def exists_at_path(self, ns_path: AnyPath, path: AnyPath) -> bool:
        fq_path = await self.mount_service.resolve_path(ns_path, path)
        return await self.filecore.exists_at_path(fq_path.ns_path, fq_path.path)

    async def get_at_path(self, ns_path: AnyPath, path: AnyPath) -> AnyFile:
        fq_path = await self.mount_service.resolve_path(ns_path, path)
        file = await self.filecore.get_by_path(fq_path.ns_path, fq_path.path)
        return _resolve_file(file, fq_path.mount_point)

    async def get_by_id(self, ns_path: AnyPath, file_id: str) -> AnyFile:
        file = await self.filecore.get_by_id(file_id)
        mount_point = None
        if file.ns_path != ns_path:
            mount_point = await self.mount_service.get_closest_by_source(
                file.ns_path, file.path, target_ns_path=str(ns_path)
            )
            if mount_point is None:
                raise File.NotFound()
        return _resolve_file(file, mount_point)

    async def list_folder(self, ns_path: AnyPath, path: AnyPath) -> list[AnyFile]:
        fq_path = await self.mount_service.resolve_path(ns_path, path)
        files = await self.filecore.list_folder(fq_path.ns_path, fq_path.path)
        return [_resolve_file(file, fq_path.mount_point) for file in files]

    async def move(
        self, ns_path: AnyPath, at_path: AnyPath, to_path: AnyPath
    ) -> AnyFile:
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
        await self.filecore.reindex(ns_path, path)

    @disk_cache(key="{file_id}:{size}", ttl=_make_thumbnail_ttl)
    async def thumbnail(
        self, file_id: str, *, size: int, ns_path: str | None = None
    ) -> tuple[AnyFile, bytes]:
        """
        Generate in-memory thumbnail with preserved aspect ratio.

        Args:
            ns_path (str): Target namespace path.
            file_id (StrOrUUID): Target file ID.
            size (int): Thumbnail dimension.

        Raises:
            File.NotFound: If file with this path does not exists.
            File.IsADirectory: If file is a directory.
            ThumbnailUnavailable: If file is not an image.

        Returns:
            tuple[AnyFile, bytes]: Tuple of file and thumbnail content.
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
