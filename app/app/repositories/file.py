from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Protocol

from app.domain.entities import File

if TYPE_CHECKING:
    from app.typedefs import StrOrPath


class IFileRepository(Protocol):
    async def get_by_path_batch(
        self, ns_path: StrOrPath, paths: Iterable[StrOrPath],
    ) -> list[File]:
        """
        Return all files with target paths. The result is sorted by path ASC.

        Args:
            ns_path (StrOrPath): Namespace path where files are located.
            paths (Iterable[StrOrPath]): Iterable of paths to look for.

        Returns:
            list[File]: List of files with target paths.
        """
