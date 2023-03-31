from __future__ import annotations

import itertools
from typing import IO, TYPE_CHECKING

from app import config
from app.app.files.domain import File, Path
from app.app.files.services.dupefinder import dhash
from app.app.files.services.metadata import readers as metadata_readers
from app.app.users.domain import Account
from app.toolkit import taskgroups, timezone

if TYPE_CHECKING:
    from app.app.files.domain import AnyPath, ContentMetadata
    from app.app.files.services import (
        DuplicateFinderService,
        FileCoreService,
        MetadataService,
        NamespaceService,
    )
    from app.app.infrastructure.storage import ContentReader
    from app.app.users.services import UserService

__all__ = ["NamespaceUseCase"]


class NamespaceUseCase:
    __slots__ = ["dupefinder", "filecore", "metadata", "namespace", "user"]

    def __init__(
        self,
        dupefinder: DuplicateFinderService,
        filecore: FileCoreService,
        metadata: MetadataService,
        namespace: NamespaceService,
        user: UserService,
    ):
        self.dupefinder = dupefinder
        self.filecore = filecore
        self.metadata = metadata
        self.namespace = namespace
        self.user = user

    async def add_file(
        self, ns_path: AnyPath, path: AnyPath, content: IO[bytes]
    ) -> File:
        """
        Saves a file to a storage and to a database. Additionally calculates and saves
        dhash and fingerprint for supported mediatypes.

        Any missing parents are also created.

        If file name is already taken, then file will be saved under a new name.
        For example - if path 'f.txt' is taken, then new path will be 'f (1).txt'.

        Args:
            ns_path (AnyPath): Namespace path where a file should be saved.
            path (AnyPath): Path where a file will be saved.
            content (IO): Actual file content.

        Raises:
            File.TooLarge: If upload file size exceeds max upload size limit.
            File.AlreadyExists: If a file in a target path already exists.
            File.MalformedPath: If path is invalid (e.g. uploading to Trash folder).
            File.NotADirectory: If one of the path parents is not a folder.
            Account.StorageQuotaExceeded: If storage quota exceeded.

        Returns:
            File: Saved file.
        """
        path = Path(path)
        if path.is_relative_to("trash"):
            raise File.MalformedPath("Uploads to the Trash folder are not allowed")

        size = content.seek(0, 2)
        if size > config.FEATURES_UPLOAD_FILE_MAX_SIZE:
            raise File.TooLarge()

        ns = await self.namespace.get_by_path(str(ns_path))
        account = await self.user.get_account(ns.owner_id)
        if account.storage_quota is not None:
            used = await self.namespace.get_space_used_by_owner_id(ns.owner_id)
            if (used + size) > account.storage_quota:
                raise Account.StorageQuotaExceeded()

        file = await self.filecore.create_file(ns_path, path, content)
        await self.dupefinder.track(file.id, content)
        await self.metadata.track(file.id, content)

        return file

    async def create_folder(self, ns_path: AnyPath, path: AnyPath) -> File:
        """
        Creates a folder with any missing parents in a namespace with a `ns_path`.

        Args:
            ns_path (Namespace): Namespace path where a folder should be created.
            path (AnyPath): Path to a folder to create.

        Raises:
            File.AlreadyExists: If folder with this path already exists.
            File.NotADirectory: If one of the path parents is not a directory.

        Returns:
            File: Created folder.
        """
        assert Path(path) not in {Path("."), Path("Trash")}
        return await self.filecore.create_folder(ns_path, path)

    async def delete_item(self, ns_path: AnyPath, path: AnyPath) -> File:
        """
        Permanently deletes a file or a folder. If path is a folder deletes a folder
        with all of its contents.

        Args:
            ns_path (AnyPath): Namespace path where file/folder should be deleted.
            path (AnyPath): Path to a file/folder to delete.

        Raises:
            File.NotFound: If a file/folder with a given path does not exists.

        Returns:
            File: Deleted file.
        """
        assert Path(path) not in {Path("."), Path("Trash")}, (
            "Can't delete Home or Trash folder."
        )
        return await self.filecore.delete(ns_path, path)

    async def download(
        self, ns_path: AnyPath, path: AnyPath
    ) -> tuple[File, ContentReader]:
        file = await self.filecore.get_by_path(ns_path, path)
        content = await self.filecore.download(file.id)
        return file, content

    async def empty_trash(self, ns_path: AnyPath) -> None:
        """
        Deletes all files and folders in the Trash folder in a target Namespace.

        Args:
            ns_path (AnyPath): Namespace path where to empty the Trash folder.
        """
        await self.filecore.empty_folder(ns_path, "trash")

    async def find_duplicates(
        self, ns_path: AnyPath, path: AnyPath, max_distance: int = 5
    ) -> list[list[File]]:
        """
        Finds all duplicate fingerprints in a folder, including sub-folders.

        Args:
            ns_path (AnyPath): Target namespace path.
            path (AnyPath): Folder path where to search for fingerprints.
            max_distance (int, optional): The maximum distance at which two fingerprints
                are considered the same. Defaults to 5.

        Returns:
            list[list[File]]: List of lists of duplicate fingerprints.
        """
        groups = await self.dupefinder.find_in_folder(ns_path, path, max_distance)
        ids = itertools.chain.from_iterable(
            (fp.file_id for fp in group)
            for group in groups
        )

        files = {
            file.id: file
            for file in await self.filecore.get_by_id_batch(ns_path, ids=ids)
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

        Args:
            ns_path (AnyPath): Namespace path where file located.
            path (AnyPath): File path

        Raises:
            File.NotFound: If file with target ID does not exist.
            ContentMetadata.NotFound: If file metadata does not exist.

        Returns:
            ContentMetadata: A file content metadata
        """
        file = await self.filecore.get_by_path(ns_path, path)
        return await self.metadata.get_by_file_id(file.id)

    async def get_file_thumbnail(
        self, ns_path: AnyPath, file_id: str, size: int
    ) -> tuple[File, bytes]:
        """
        Generates in-memory thumbnail with preserved aspect ratio.

        Args:
            ns_path (ns_path): Namespace where a file is located.
            file_id (StrOrUUID): Target file ID.
            size (int): Thumbnail dimension.

        Raises:
            File.NotFound: If file with target ID does not exist.
            File.IsADirectory: If file is a directory.
            ThumbnailUnavailable: If file is not an image.

        Returns:
            tuple[File, bytes]: Tuple of file and thumbnail content.
        """
        file, thumbnail = await self.filecore.thumbnail(file_id, size=size)
        # normally we would check if file exists before calling `filecore.thumbnail`,
        # but since thumbnail is cached it is faster to hit cache and then
        # check if file belongs to a namespace
        if str(file.ns_path) != str(ns_path):
            raise File.NotFound()
        return file, thumbnail

    async def get_item_at_path(self, ns_path: AnyPath, path: AnyPath) -> File:
        return await self.filecore.get_by_path(ns_path, path)

    async def list_folder(self, ns_path: AnyPath, path: AnyPath) -> list[File]:
        """
        Lists all files in the folder at a given path.

        Use "." to list all files and folders in the home folder. Note, that Trash
        folder will not be present in the response.

        Args:
            ns_path (AnyPath): Namespace path where a folder located.
            path (AnyPath): Path to a folder in the target namespace.

        Raises:
            File.NotFound: If folder at this path does not exists.
            File.NotADirectory: If path points to a file.

        Returns:
            List[File]: List of all files/folders in a folder with a target path.
        """
        files = await self.filecore.list_folder(ns_path, path)
        if path == ".":
            special_paths = {Path("."), Path("trash")}
            return [file for file in files if file.path not in special_paths]
        return files

    async def move_item(
        self, ns_path: AnyPath, path: AnyPath, next_path: AnyPath
    ) -> File:
        """
        Moves a file or a folder to a different location in the target Namespace.
        If the source path is a folder all its contents will be moved.

        Args:
            ns_path (AnyPath): Namespace path where file/folder should be moved
            path (AnyPath): Path to be moved.
            next_path (AnyPath): Path that is the destination.

        Raises:
            File.NotFound: If source path does not exists.
            File.AlreadyExists: If some file already in the destination path.
            File.MissingParent: If 'next_path' parent does not exists.
            File.NotADirectory: If one of the 'next_path' parents is not a folder.

        Returns:
            File: Moved file/folder.
        """
        assert Path(path) not in {Path("."), Path("Trash")}, (
            "Can't move Home or Trash folder."
        )
        return await self.filecore.move(ns_path, path, next_path)

    async def move_item_to_trash(self, ns_path: AnyPath, path: AnyPath) -> File:
        """
        Moves a file or folder to the Trash folder in the target Namespace.
        If path is a folder all its contents will be moved.
        If file with the same name already in the Trash, then path will be renamed.

        Args:
            namespace (Namespace): Namespace where path located.
            path (AnyPath): Path to a file or folder to be moved to the Trash folder.

        Raises:
            File.NotFound: If source path does not exists.

        Returns:
            File: Moved file.
        """
        next_path = Path("Trash") / Path(path).name

        if await self.filecore.exists_at_path(ns_path, next_path):
            timestamp = f"{timezone.now():%H%M%S%f}"
            next_path = next_path.with_stem(f"{next_path.stem} {timestamp}")

        return await self.filecore.move(ns_path, path, next_path)

    async def reindex(self, ns_path: AnyPath) -> None:
        """
        Reindexes all files in the given namespace.

        This method creates files that are missing in the database, but present in the
        storage and removes files that are present in the database, but missing in the
        storage.

        Args:
            ns_path (AnyPath): Namespace path to reindex.

        Raises:
            Namespace.NotFound: If namespace does not exist.
            File.NotADirectory: If given path does not exist.
        """
        # ensure namespace exists
        await self.namespace.get_by_path(str(ns_path))
        await self.filecore.reindex(ns_path, ".")

    async def reindex_contents(self, ns_path: AnyPath) -> None:
        """
        Restores additional information about files, such as fingerprint and content
        metadata.

        Args:
            ns_path (AnyPath): Namespace path to reindex.
        """
        ns_path = str(ns_path)
        batch_size = 500
        types = tuple(dhash.SUPPORTED_TYPES | metadata_readers.SUPPORTED_TYPES)
        batches = self.filecore.iter_by_mediatypes(
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
        content_reader = await self.filecore.download(file.id)
        for tracker in trackers:
            await tracker.add(file.id, await content_reader.stream())
