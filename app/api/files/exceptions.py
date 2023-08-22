from __future__ import annotations

import abc
from typing import TYPE_CHECKING

from app.api.exceptions import APIError
from app.app.files.domain import Path

if TYPE_CHECKING:
    from app.app.files.domain import AnyPath


class FilesError(APIError):
    def __init__(self, message: str | None = None, path: AnyPath | None = None):
        super().__init__(message)
        assert path is not None, "Missing required argument: 'path'"
        self.message = self.get_message(path)

    @abc.abstractmethod
    def get_message(self, path: AnyPath) -> str:  # pragma: no cover
        raise NotImplementedError()


class DownloadNotFound(APIError):
    status_code = 404
    code = "DOWNLOAD_NOT_FOUND"
    code_verbose = "Download not found"
    default_message = "Download is expired or doesn't exist"


class FileActionNotAllowed(APIError):
    status_code = 403
    code = "ACTION_NOT_ALLOWED"
    code_verbose = "Action not allowed"
    default_message = "You don't have permission to perform that action"


class FileAlreadyDeleted(FilesError):
    status_code = 400
    code = "ALREADY_DELETED"
    code_verbose = "Already deleted"
    default_message = "File '{name}' is already in the Trash"

    def get_message(self, path: AnyPath) -> str:
        path = Path(path)
        return self.message.format(name=path.name)


class FileAlreadyExists(FilesError):
    status_code = 400
    code = "FILE_ALREADY_EXISTS"
    code_verbose = "File already exists"
    default_message = "The name '{name}' at path {parent} is already taken"

    def get_message(self, path: AnyPath) -> str:
        path = Path(path)
        return self.message.format(name=path.name, parent=path.parent)


class FileContentMetadataNotFound(FilesError):
    status_code = 404
    code = "CONTENT_METADATA_NOT_FOUND"
    code_verbose = "No metadata"
    default_message = "File at path {path} doesn't have any associated metadata"

    def get_message(self, path: AnyPath) -> str:
        return self.message.format(path=path)


class IsADirectory(FilesError):
    status_code = 400
    code = "IS_A_DIRECTORY"
    code_verbose = "Path is a directory"
    default_message = "Expected the path '{path}' to be a file, but it is a folder"

    def get_message(self, path: AnyPath) -> str:
        return self.message.format(path=path)


class MalformedPath(APIError):
    status_code = 400
    code = "MALFORMED_PATH"
    code_verbose = "Malformed path"
    default_message = ""


class NotADirectory(FilesError):
    status_code = 400
    code = "NOT_A_DIRECTORY"
    code_verbose = "Not a directory"
    default_message = (
        "Expected the path '{path}' and its parents to be folders, not files"
    )

    def get_message(self, path: AnyPath) -> str:
        return self.message.format(path=path)


class PathNotFound(FilesError):
    status_code = 404
    code = "PATH_NOT_FOUND"
    code_verbose = "Path not found"
    default_message = "The path '{path}' does not exists"

    def get_message(self, path: AnyPath) -> str:
        return self.message.format(path=path)


class StorageQuotaExceeded(APIError):
    status_code = 400
    code = "STORAGE_QUOTA_EXCEEDED"
    code_verbose = "Storage Quota Exceeded"
    default_message = "Storage is full - consider removing files you don't need"


class ThumbnailUnavailable(FilesError):
    status_code = 400
    code = "THUMBNAIL_UNAVAILABLE"
    code_verbose = "Thumbnail unavailable"
    default_message = "Can't generate thumbnail for a file '{name}' at path '{parent}'"

    def get_message(self, path: AnyPath) -> str:
        path = Path(path)
        return self.message.format(name=path.name, parent=path.parent)


class UploadFileTooLarge(APIError):
    status_code = 400
    code = "UPLOAD_FILE_TOO_LARGE"
    code_verbose = "Upload too large"
    default_message = "File exceeds maximum upload size"
