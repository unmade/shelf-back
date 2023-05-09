from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.app.files.domain import AnyPath, MountPoint

__all__ = ["IMountRepository"]


class IMountRepository(Protocol):
    async def get_closest(self, ns_path: AnyPath, path: AnyPath) -> MountPoint:
        """
        Returns closest mount for a path in a given namespace.

        Args:
            ns_path (AnyPath): Target namespace.
            path (AnyPath): Path to the mount point or path inside mount point.

        Raises:
            MountPoint.NotFound: If there is no MountPoint at a given path.

        Returns:
            MountPoint: Resolved MountPoint for a given path.
        """

    async def get_closest_by_source(
        self, source_ns_path: AnyPath, source_path: AnyPath, target_ns_path: AnyPath
    ) -> MountPoint:
        """
        Returns mount point in the target namespace for a source file.

        Args:
            source_ns_path (AnyPath): Real namespace path of a mounted file.
            source_path (AnyPath): Real path of a mounted file.
            target_ns_path (AnyPath): Namespace where file is mounted.

        Returns:
            MountPoint: Resolved MountPoint for a given file.
        """
