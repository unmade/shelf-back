from __future__ import annotations

from typing import TYPE_CHECKING

from app.app.files.domain import FullyQualifiedPath, MountedFile

if TYPE_CHECKING:
    from app.app.files.domain import AnyFile, AnyPath
    from app.app.files.services import FileCoreService
    from app.app.files.services.file.mount import MountService


def _resolve_file(file: AnyFile, fq_path: FullyQualifiedPath) -> AnyFile:
    if fq_path.mount_point is None:
        return file

    if isinstance(file, MountedFile):
        return file

    relpath = str(file.path)[len(str(fq_path.mount_point.source.path)) + 1:]
    path = fq_path.mount_point.display_path / relpath

    return MountedFile(
        id=file.id,
        ns_path=fq_path.mount_point.folder.ns_path,
        name=path.name,
        path=path,
        size=file.size,
        mtime=file.mtime,
        mediatype=file.mediatype,
        mount_point=fq_path.mount_point,
    )


class FileService:
    __slots__ = ["filecore", "mount_service"]

    def __init__(self, filecore: FileCoreService, mount_service: MountService):
        self.filecore = filecore
        self.mount_service = mount_service

    async def list_folder(self, ns_path: AnyPath, path: AnyPath) -> list[AnyFile]:
        fq_path = await self.mount_service.resolve_path(ns_path, path)
        files = await self.filecore.list_folder(fq_path.ns_path, fq_path.path)
        return [_resolve_file(file, fq_path) for file in files]
