from __future__ import annotations

from typing import IO, TYPE_CHECKING

from app import config, errors

if TYPE_CHECKING:
    from app.app.services import NamespaceService, UserService
    from app.domain.entities import File
    from app.typedefs import StrOrPath

__all__ = ["UploadFile"]


class UploadFile:
    def __init__(self, namespace_service: NamespaceService, user_service: UserService):
        self.namespace_service = namespace_service
        self.user_service = user_service

    async def __call__(
        self, ns_path: StrOrPath, path: StrOrPath, content: IO[bytes],
    ) -> File:
        """
        Uploads a file to a namespace.

        If file name is already taken, then the file automatically renamed to a new one.
        For example - a path 'f.txt' will be saved as 'f (1).txt' in case its taken.

        Args:
            ns_path (StrOrPath): Namespace path where a file should be saved.
            path (StrOrPath): Path where a file will be saved.
            content (IO): Actual file.

        Raises:
            FileTooLarge: If upload file size exceeds max upload size limit.
            MalformedPath: If upload path is invalid (e.g. uploading to Trash folder).
            NotADirectory: If one of the path parents is not a folder.
            StorageQuotaExceeded: If storage quota exceeded.

        Returns:
            File: Uploaded file.
        """
        path = str(path)
        if path.lower() == "trash" or path.lower().startswith("trash/"):
            raise errors.MalformedPath("Uploads to the Trash folder are not allowed")

        size = content.seek(0, 2)
        if size > config.FEATURES_UPLOAD_FILE_MAX_SIZE:
            raise errors.FileTooLarge()

        ns = await self.namespace_service.get_by_path(str(ns_path))
        account = await self.user_service.get_account(ns.owner_id)
        if account.storage_quota is not None:
            used = await self.namespace_service.get_space_used_by_owner_id(ns.owner_id)
            if (used + size) > account.storage_quota:
                raise errors.StorageQuotaExceeded()

        return await self.namespace_service.add_file(ns_path, path, content)
