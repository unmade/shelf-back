from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple, Protocol

from app.app.files.domain import MountPoint, Path
from app.app.files.repositories import IMountRepository
from app.app.files.repositories.mount import MountPointUpdate

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.app.files.domain import AnyPath

    class IServiceDatabase(Protocol):
        mount: IMountRepository

__all__ = [
    "FullyQualifiedPath",
    "MountService",
]


class FullyQualifiedPath(NamedTuple):
    """
    A fully-qualified path.

    The `ns_path` and `path` always point to the actual file location. The optional
    `mount point` field specifies whether the file is mounted.

    Examples:
        a FQ path to the "folder/f.txt" in the "admin" namespace:

        >>> FullyQualifiedPath("admin", "folder/f.txt")

        Let's say the "folder" mounted under name "SharedFolder" in the "user"
        namespace. In that case the path "SharedFolder/f.txt" in the "user" namespace
        can be represented as the following FQ path:

        >>> FullyQualifiedPath(
        >>>    "admin",
        >>>    "folder/f.txt",
        >>>    mount_point=MountPoint(
        >>>        source=MountPoint.Source(
        >>>            ns_path="admin",
        >>>            path="folder",
        >>>        ),
        >>>        folder=MountPoint.ContainingFolder(
        >>>            ns_path="user",
        >>>            path=".",
        >>>        ),
        >>>        display_name="SharedFolder",
        >>>    ),
        >>>)
    """
    ns_path: str
    path: Path
    mount_point: MountPoint | None = None

    def is_mount_point(self) -> bool:
        if self.mount_point is None:
            return False
        return self.mount_point.source.path == self.path


class MountService:
    __slots__ = ["db"]

    def __init__(self, database: IServiceDatabase) -> None:
        self.db = database

    async def create(
        self,
        source: tuple[str, AnyPath],
        at_folder: tuple[str, AnyPath],
        name: str,
    ) -> MountPoint:
        """Creates a mount point at a target folder pointing to a source file."""
        assert source[0] != at_folder[0], "Can't mount within the same namespace."

        return await self.db.mount.save(
            MountPoint(
                source=MountPoint.Source(
                    ns_path=source[0],
                    path=Path(source[1]),
                ),
                folder=MountPoint.ContainingFolder(
                    ns_path=at_folder[0],
                    path=Path(at_folder[1]),
                ),
                display_name=name,
            ),
        )

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


    async def move(self, ns_path: AnyPath, at_path: AnyPath, to_path: AnyPath):
        at_path = Path(at_path)
        to_path = Path(to_path)
        mount_point = await self.db.mount.get_closest(ns_path, at_path)
        return await self.db.mount.update(
            mount_point,
            fields=MountPointUpdate(
                folder=to_path.parent,
                display_name=to_path.name,
            )
        )

    async def resolve_path(self, ns_path: AnyPath, path: AnyPath) -> FullyQualifiedPath:
        """Resolves path in the target namespace to a fully-qualified path."""
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

    async def reverse_path_batch(
        self, ns_path: AnyPath, sources: Sequence[tuple[AnyPath, AnyPath]]
    ) -> dict[tuple[AnyPath, AnyPath], FullyQualifiedPath]:
        """
        Given an iterable of tuples, where the first element is a namespace and the
        second elemnt is a path returns a fully-qualified path within a `ns_path`
        for each item in the list.
        """
        if not sources:
            return {}

        # fetching all mount points is faster than filtering by possible source paths
        # on the database level
        mount_points = await self.db.mount.list_all(ns_path)
        mps_by_ns: dict[str, list[MountPoint]] = {}
        for mp in mount_points:
            mps_by_ns.setdefault(mp.source.ns_path, []).append(mp)

        result: dict[tuple[AnyPath, AnyPath], FullyQualifiedPath] = {}
        for ns_path, path in sources:
            mps = mps_by_ns.get(str(ns_path), [])
            for mp in mps:
                if Path(path).is_relative_to(mp.source.path):
                    result[ns_path, path] = FullyQualifiedPath(
                        ns_path=str(ns_path),
                        path=Path(path),
                        mount_point=mp,
                    )

        return result
