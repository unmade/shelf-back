from __future__ import annotations

from typing import IO, TYPE_CHECKING

from app.app.files.domain import File, MountedFile, MountPoint
from app.cache import disk_cache

from . import thumbnails

if TYPE_CHECKING:
    from app.app.files.domain import AnyFile, AnyPath
    from app.app.files.services import FileCoreService
    from app.app.files.services.file.mount import MountService
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

    async def get_at_path(self, ns_path: AnyPath, path: AnyPath) -> AnyFile:
        fq_path = await self.mount_service.resolve_path(ns_path, path)
        file = await self.filecore.get_by_path(fq_path.ns_path, fq_path.path)
        return _resolve_file(file, fq_path.mount_point)

    async def list_folder(self, ns_path: AnyPath, path: AnyPath) -> list[AnyFile]:
        fq_path = await self.mount_service.resolve_path(ns_path, path)
        files = await self.filecore.list_folder(fq_path.ns_path, fq_path.path)
        return [_resolve_file(file, fq_path.mount_point) for file in files]

    @disk_cache(key="{file_id}:{size}", ttl=_make_thumbnail_ttl)
    async def thumbnail(
        self, ns_path: str, file_id: str, *, size: int
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
        if file.ns_path != ns_path:
            mount_point = await self.mount_service.get_closest_by_source(
                file.ns_path, file.path, target_ns_path=ns_path
            )
            if mount_point is None:
                raise File.NotFound() from None

        content = await content_reader.stream()
        thumbnail = await thumbnails.thumbnail(content, size=size)
        return _resolve_file(file, mount_point), thumbnail
