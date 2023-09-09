from __future__ import annotations

import itertools
from io import BytesIO
from typing import TYPE_CHECKING, AsyncIterator, cast

from app.app.files.domain import AnyFile, File, Path
from app.app.files.domain.file import ThumbnailUnavailable
from app.app.files.services.dupefinder import dhash
from app.app.files.services.metadata import readers as metadata_readers
from app.app.users.domain import Account
from app.config import config
from app.toolkit import taskgroups, timezone

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.audit.services import AuditTrailService
    from app.app.files.domain import AnyPath, ContentMetadata, IFileContent
    from app.app.files.services import (
        DuplicateFinderService,
        FileService,
        MetadataService,
        NamespaceService,
    )
    from app.app.users.services import UserService

__all__ = ["NamespaceUseCase"]


class NamespaceUseCase:
    __slots__ = [
        "audit_trail", "dupefinder", "file", "metadata", "namespace", "user"
    ]

    def __init__(
        self,
        audit_trail: AuditTrailService,
        dupefinder: DuplicateFinderService,
        file: FileService,
        metadata: MetadataService,
        namespace: NamespaceService,
        user: UserService,
    ):
        self.audit_trail = audit_trail
        self.dupefinder = dupefinder
        self.file = file
        self.metadata = metadata
        self.namespace = namespace
        self.user = user

    async def add_file(
        self, ns_path: AnyPath, path: AnyPath, content: IFileContent
    ) -> AnyFile:
        """
        Saves a file to a storage and to a database. Additionally calculates and saves
        dhash and fingerprint for supported mediatypes.

        Any missing parents are created.

        If file name is already taken, then file will be saved under a new name.
        For example - if path 'f.txt' is taken, then new path will be 'f (1).txt'.

        Raises:
            Account.StorageQuotaExceeded: If storage quota exceeded.
            File.ActionNotAllowed: If adding a file is not allowed.
            File.AlreadyExists: If a file in a target path already exists.
            File.MalformedPath: If path is invalid (e.g. uploading to Trash folder).
            File.NotADirectory: If one of the path parents is not a folder.
            File.TooLarge: If upload file size exceeds max upload size limit.

        Returns:
            AnyFile: Saved file.
        """
        path = Path(path)
        if path.is_relative_to("trash"):
            raise File.MalformedPath("Uploads to the Trash folder are not allowed")

        if content.size > config.features.upload_file_max_size:
            raise File.TooLarge()

        ns = await self.namespace.get_by_path(str(ns_path))
        account = await self.user.get_account(ns.owner_id)
        if account.storage_quota is not None:
            used = await self.namespace.get_space_used_by_owner_id(ns.owner_id)
            if (used + content.size) > account.storage_quota:
                raise Account.StorageQuotaExceeded()

        file = await self.file.create_file(ns_path, path, content)
        await self.dupefinder.track(file.id, content)
        await self.metadata.track(file.id, content)

        taskgroups.schedule(self.audit_trail.file_added(file))
        return file

    async def create_folder(self, ns_path: AnyPath, path: AnyPath) -> AnyFile:
        """
        Creates a folder with any missing parents in a namespace with a `ns_path`.

        Raises:
            File.ActionNotAllowed: If creating a folder is not allowed.
            File.AlreadyExists: If folder with this path already exists.
            File.NotADirectory: If one of the path parents is not a directory.
        """
        assert Path(path) not in {Path("."), Path("Trash")}
        folder = await self.file.create_folder(ns_path, path)
        taskgroups.schedule(self.audit_trail.folder_created(folder))
        return folder

    async def delete_item(self, ns_path: AnyPath, path: AnyPath) -> AnyFile:
        """
        Permanently deletes a file or a folder. If path is a folder deletes a folder
        with all of its contents.

        Raises:
            File.ActionNotAllowed: If deleting an item is not allowed.
            File.NotFound: If a file/folder with a given path does not exist.
        """
        assert Path(path) not in {Path("."), Path("Trash")}, (
            "Can't delete Home or Trash folder."
        )
        return await self.file.delete(ns_path, path)

    async def download(
        self, ns_path: AnyPath, path: AnyPath
    ) -> tuple[AnyFile, AsyncIterator[bytes]]:
        """
        Downloads a file at a given path.

        Raises:
            File.ActionNotAllowed: If downloading an item is not allowed.
            File.IsADirectory: If file is a directory.
            File.NotFound: If a file with a given path does not exist.
        """
        return await self.file.download(ns_path, path)

    async def empty_trash(self, ns_path: AnyPath) -> None:
        """Deletes all files and folders in the Trash folder in a target namespace."""
        await self.file.empty_folder(ns_path, "trash")
        taskgroups.schedule(self.audit_trail.trash_emptied())

    async def find_duplicates(
        self, ns_path: AnyPath, path: AnyPath, max_distance: int = 5
    ) -> list[list[AnyFile]]:
        """
        Finds all duplicate fingerprints in a folder, including sub-folders.

        The `max_distance` arg is maximum distance at which two fingerprints
        are considered the same. Defaults to 5.
        """
        groups = await self.dupefinder.find_in_folder(ns_path, path, max_distance)
        ids = itertools.chain.from_iterable(  # pragma: no branch
            (fp.file_id for fp in group)
            for group in groups
        )

        files = {
            file.id: file
            for file in await self.file.get_by_id_batch(ns_path, ids=ids)
        }

        return [
            [files[fp.file_id] for fp in group]
            for group in groups
        ]

    async def get_file_metadata(
        self, ns_path: AnyPath, path: AnyPath
    ) -> ContentMetadata:
        """
        Returns a file content metadata.

        Raises:
            File.ActionNotAllowed: If getting a file is not allowed.
            File.NotFound: If file with target ID does not exist.
            ContentMetadata.NotFound: If file metadata does not exist.
        """
        file = await self.file.get_at_path(ns_path, path)
        return await self.metadata.get_by_file_id(file.id)

    async def get_file_thumbnail(
        self, ns_path: AnyPath, file_id: UUID, size: int
    ) -> tuple[AnyFile, bytes]:
        """
        Generates in-memory thumbnail with preserved aspect ratio.

        Raises:
            File.ActionNotAllowed: If thumbnailing a file is not allowed.
            File.NotFound: If file with target ID does not exist.
            File.IsADirectory: If file is a directory.
            ThumbnailUnavailable: If file is not an image.
        """
        file = await self.file.get_by_id(ns_path, file_id)
        if file.size > config.features.max_file_size_to_thumbnail:
            raise ThumbnailUnavailable() from None
        return cast(
            tuple[AnyFile, bytes],
            await self.file.thumbnail(file_id, size=size, ns_path=ns_path)
        )

    async def get_item_at_path(self, ns_path: AnyPath, path: AnyPath) -> AnyFile:
        """
        Returns a file at a given path.

        Raises:
            File.ActionNotAllowed: If getting a file is not allowed.
            File.NotFound: If file does not exist at a given path.
        """
        return await self.file.get_at_path(ns_path, path)

    async def list_folder(self, ns_path: AnyPath, path: AnyPath) -> list[AnyFile]:
        """
        Lists all files in the folder at a given path.

        Use "." to list all files and folders in the home folder. Note, that Trash
        folder is never present in the response.

        Raises:
            File.ActionNotAllowed: If listing a folder is not allowed.
            File.NotFound: If folder at this path does not exist.
            File.NotADirectory: If path points to a file.
        """
        files = await self.file.list_folder(ns_path, path)
        if path == ".":
            special_paths = {Path("."), Path("trash")}
            return [file for file in files if file.path not in special_paths]
        return files

    async def move_item(
        self, ns_path: AnyPath, path: AnyPath, next_path: AnyPath
    ) -> AnyFile:
        """
        Moves a file or a folder to a different location in the target Namespace.
        If the source path is a folder all its contents will be moved.

        Raises:
            File.ActionNotAllowed: If moving an item is not allowed.
            File.AlreadyExists: If some file already in the destination path.
            File.MalformedPath: If `path` or `next_path` is invalid.
            File.MissingParent: If 'next_path' parent does not exists.
            File.NotFound: If source path does not exists.
            File.NotADirectory: If one of the 'next_path' parents is not a folder.
        """
        assert Path(path) not in {Path("."), Path("Trash")}, (
            "Can't move Home or Trash folder."
        )
        file = await self.file.move(ns_path, path, next_path)
        taskgroups.schedule(self.audit_trail.file_moved(file))
        return file

    async def move_item_to_trash(self, ns_path: AnyPath, path: AnyPath) -> AnyFile:
        """
        Moves a file or folder to the Trash folder in the target Namespace.
        If path is a folder all its contents will be moved.
        If file with the same name already in the Trash, then path will be renamed.

        Raises:
            File.ActionNotAllowed: If moving an item is not allowed.
            File.NotFound: If source path does not exists.
        """
        next_path = Path("Trash") / Path(path).name

        if await self.file.exists_at_path(ns_path, next_path):
            timestamp = f"{timezone.now():%H%M%S%f}"
            next_path = next_path.with_stem(f"{next_path.stem} {timestamp}")

        file = await self.file.move(ns_path, path, next_path)
        taskgroups.schedule(self.audit_trail.file_trashed(file))
        return file

    async def reindex(self, ns_path: AnyPath) -> None:
        """
        Reindexes all files in the given namespace.

        This method creates files that are missing in the database, but present in the
        storage and removes files that are present in the database, but missing in the
        storage.

        Raises:
            File.NotADirectory: If given path does not exist.
            Namespace.NotFound: If namespace does not exist.
        """
        # ensure namespace exists
        await self.namespace.get_by_path(str(ns_path))
        await self.file.reindex(ns_path, ".")

    async def reindex_contents(self, ns_path: AnyPath) -> None:
        """
        Restores additional information about files, such as fingerprint and content
        metadata.
        """
        ns_path = str(ns_path)
        batch_size = 500
        types = tuple(dhash.SUPPORTED_TYPES | metadata_readers.SUPPORTED_TYPES)
        batches = self.file.filecore.iter_by_mediatypes(
            ns_path, mediatypes=types, batch_size=batch_size
        )

        async for files in batches:
            async with (
                self.dupefinder.track_batch() as dupefinder_tracker,
                self.metadata.track_batch() as metadata_tracker,
            ):
                await taskgroups.gather(*(
                    self._reindex_content(
                        file,
                        trackers=[dupefinder_tracker, metadata_tracker],
                    )
                    for file in files
                ))

    async def _reindex_content(self, file: File, trackers) -> None:
        _, chunks = await self.file.filecore.download(file.id)
        content = BytesIO(b"".join([chunk async for chunk in chunks]))
        for tracker in trackers:
            await tracker.add(file.id, content)
