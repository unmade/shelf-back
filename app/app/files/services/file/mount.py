from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.app.files.domain import FullyQualifiedPath, MountPoint, Path
from app.app.files.repositories.mount import IMountRepository

if TYPE_CHECKING:
    from app.app.files.domain import AnyPath

    class IServiceDatabase(Protocol):
        mount: IMountRepository


class MountService:
    __slots__ = ["db"]

    def __init__(self, database: IServiceDatabase) -> None:
        self.db = database

    async def get_closest_by_source(
        self, source_ns_path: str, source_path: AnyPath, target_ns_path: str
    ) -> MountPoint | None:
        try:
            return await self.db.mount.get_closest_by_source(
                source_ns_path=source_ns_path,
                source_path=source_path,
                target_ns_path=target_ns_path,
            )
        except MountPoint.NotFound:
            return None

    async def resolve_path(self, ns_path: AnyPath, path: AnyPath) -> FullyQualifiedPath:
        """
        Returns fully-qualified path if the path is a mount point or inside mount point,
        otherwise returns path unchanged.
        """
        try:
            mount = await self.db.mount.get_closest(ns_path, path)
        except MountPoint.NotFound:
            return FullyQualifiedPath(ns_path=str(ns_path), path=Path(path))

        relpath = str(path)[len(str(mount.display_path)) + 1:].strip("/")
        return FullyQualifiedPath(
            ns_path=mount.source.ns_path,
            path=mount.source.path / relpath,
            mount_point=mount,
        )
