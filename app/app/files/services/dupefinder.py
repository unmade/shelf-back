from __future__ import annotations

import asyncio
import contextlib
from collections import defaultdict
from typing import IO, TYPE_CHECKING, AsyncIterator, Protocol

from app import hashes
from app.app.files.domain import Fingerprint, mediatypes

if TYPE_CHECKING:
    from app.app.files.repositories import IFingerprintRepository
    from app.app.files.repositories.fingerprint import MatchResult
    from app.typedefs import StrOrPath

    class IServiceDatabase(Protocol):
        fingerprint: IFingerprintRepository

__all__ = ["DuplicateFinderService"]


class DuplicateFinderService:
    """A service to find file duplicates."""

    __slots__ = ["db"]

    def __init__(self, database: IServiceDatabase):
        self.db = database

    @staticmethod
    def _group(result: MatchResult, max_distance: int) -> list[list[Fingerprint]]:
        """
        Groups fingerprints with distance equal or lesser than `max_distance`.

        Args:
            result (MatchResult): an adjacency list of matching fingerprints.

        Returns:
            list[list[Fingerprint]]: Fingerprints grouped by the 'same' value.
        """
        def _traverse(graph, node, visited=set()):  # noqa: B006
            """Returns list of all direct/indirect adjacent nodes for a given node."""
            nodes: list[Fingerprint] = []
            if node in visited:
                return nodes
            visited.add(node)
            nodes.append(node)
            for adjacent in graph[node]:
                nodes.extend(_traverse(graph, adjacent))
            return nodes

        # calculate distance and store it as adjacency list
        visited = set()
        matches = defaultdict(list)
        for fp, dupes in result.items():
            for dupe in dupes:
                if (fp, dupe) in visited:
                    continue
                visited.add((dupe, fp))
                distance = (fp.value ^ dupe.value).bit_count()
                if distance <= max_distance:
                    matches[fp].append(dupe)
                    matches[dupe].append(fp)

        # traverse adjacency list to group direct/indirect adjacent nodes
        return [
            group
            for node in matches
            if (group := _traverse(matches, node))
        ]

    async def find_in_folder(
        self, ns_path: StrOrPath, path: StrOrPath, max_distance: int = 5
    ) -> list[list[Fingerprint]]:
        """
        Finds all duplicate fingerprints in a folder, including sub-folders.

        Args:
            ns_path (StrOrPath): Target namespace.
            path (StrOrPath): Folder path where to search for fingerprints.
            max_distance (int, optional): The maximum distance at which two fingerprints
                are considered the same. Defaults to 5.

        Returns:
            list[list[Fingerprint]]: List of lists of duplicate fingerprints.
        """
        prefix = "" if path == "." else f"{path}/"
        intersection = await self.db.fingerprint.intersect_all_with_prefix(
            ns_path, prefix=prefix
        )
        return self._group(intersection, max_distance=max_distance)

    async def track(self, file_id: str, content: IO[bytes]) -> None:
        """
        Tracks fingerprints for a given file content.

        Args:
            file_id (str): File ID.
            content (IO[bytes]): File Content.

        Raises:
            Fingerprint.AlreadyExists: If fingerprint for a file already exists.
            File.NotFound: If a file with specified file ID doesn't exist.
        """
        mediatype = mediatypes.guess(content)
        dhash = hashes.dhash(content, mediatype=mediatype)
        if dhash is None:
            return

        await self.db.fingerprint.save(
            Fingerprint(file_id, value=dhash)
        )

    @contextlib.asynccontextmanager
    async def track_batch(self) -> AsyncIterator[_Tracker]:
        tracker = _Tracker()
        try:
            yield tracker
        finally:
            await self.db.fingerprint.save_batch(tracker)


class _Tracker:
    def __init__(self):
        self._items = []

    async def add(self, file_id: str, content: IO[bytes]) -> None:
        loop = asyncio.get_running_loop()
        mediatype = mediatypes.guess(content)
        dhash = await loop.run_in_executor(None, hashes.dhash, content, mediatype)
        if dhash is None:
            return

        self._items.append(
            Fingerprint(file_id, value=dhash)
        )

    def __eq__(self, other) -> bool:
        if isinstance(other, _Tracker):
            return self._items == other._items
        return NotImplemented

    def __iter__(self):
        return iter(self._items)
