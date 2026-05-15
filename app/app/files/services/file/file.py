from __future__ import annotations

from typing import TYPE_CHECKING

from app.app.files.domain import File, Path

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable
    from datetime import datetime
    from uuid import UUID

    from app.app.blobs.domain import IBlobContent
    from app.app.files.domain import AnyPath
    from app.app.files.services.file import FileCoreService


class FileService:
    """
    A service to manipulate files inside a namespace.

    Historically that service was a wrapper to resolve regular and in-app shared files.
    Now it simply remains a thin-wrapper over FileCoreService.
    """

    __slots__ = ["filecore"]

    def __init__(self, filecore: FileCoreService):
        self.filecore = filecore

    async def create_file(
        self,
        ns_path: AnyPath,
        path: AnyPath,
        content: IBlobContent,
        modified_at: datetime | None = None,
    ) -> File:
        """
        Creates a new file with any missing parents. If file name is taken, then file
        automatically renamed to a next available name.
        """
        path = await self.get_available_path(ns_path, path)
        return await self.filecore.create_file(
            ns_path, path, content, modified_at
        )

    async def create_folder(self, ns_path: AnyPath, path: AnyPath) -> File:
        """
        Creates a folder with any missing parents in a namespace with a `ns_path`.
        """
        return await self.filecore.create_folder(ns_path, path)

    async def delete(self, ns_path: AnyPath, path: AnyPath) -> File:
        """
        Permanently deletes a file. If path is a folder deletes a folder with all of its
        contents.
        """
        return await self.filecore.delete(ns_path, path)

    async def download(
        self, ns_path: AnyPath, path: AnyPath
    ) -> tuple[File, AsyncIterator[bytes]]:
        """Downloads a file at a given path."""
        file = await self.filecore.get_by_path(ns_path, path)
        _, content = await self.filecore.download(file.id)
        return file, content

    async def download_by_id(self, file_id: UUID) -> tuple[File, AsyncIterator[bytes]]:
        """Downloads a file with the given ID."""
        file, content = await self.filecore.download(file_id)
        return file, content

    def download_folder(self, owner_id: UUID, path: AnyPath) -> Iterable[bytes]:
        """Downloads a folder at a given path."""
        return self.filecore.download_folder(owner_id, path)

    async def empty_folder(self, ns_path: AnyPath, path: AnyPath) -> None:
        """Delete all files and folder at a given folder."""
        await self.filecore.empty_folder(ns_path, path)

    async def exists_at_path(self, ns_path: AnyPath, path: AnyPath) -> bool:
        """Returns True if file exists at a given path, False otherwise."""
        return await self.filecore.exists_at_path(ns_path, path)

    async def get_at_path(self, ns_path: AnyPath, path: AnyPath) -> File:
        """Returns a file at a given path."""
        return await self.filecore.get_by_path(ns_path, path)

    async def get_available_path(self, ns_path: AnyPath, path: AnyPath) -> Path:
        """
        Returns a modified path if the current one is already taken, otherwise returns
        path unchanged.
        """
        return await self.filecore.get_available_path(ns_path, path)

    async def get_by_id(self, ns_path: AnyPath, file_id: UUID) -> File:
        """Returns a file by ID."""
        file = await self.filecore.get_by_id(file_id)
        if file.ns_path != str(ns_path):
            raise File.NotFound()
        return file

    async def get_by_id_batch(
        self, ns_path: AnyPath, ids: Iterable[UUID]
    ) -> list[File]:
        """Returns files by ID in the target namespace."""
        files = await self.filecore.get_by_id_batch(ids)
        return [file for file in files if file.ns_path == str(ns_path)]

    async def list_folder(self, ns_path: AnyPath, path: AnyPath) -> list[File]:
        """
        Lists all files in the folder at a given path. Use "." to list top-level files
        and folders.
        """
        return await self.filecore.list_folder(ns_path, path)

    async def move(
        self, ns_path: AnyPath, at_path: AnyPath, to_path: AnyPath
    ) -> File:
        """
        Moves a file or a folder to a different location in the target Namespace.
        If the source path is a folder all its contents will be moved.
        """
        return await self.filecore.move(
            at=(ns_path, at_path),
            to=(ns_path, to_path),
        )
