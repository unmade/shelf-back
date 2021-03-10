from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from app.api.exceptions import APIError

if TYPE_CHECKING:
    from app.typedefs import StrOrPath


class FilesError(APIError):
    def __init__(self, message: Optional[str] = None, path: Optional[StrOrPath] = None):
        super().__init__(message)
        assert path is not None, "Missing required argument: 'path'"
        self.message = self.get_message(path)

    def get_message(self, path: StrOrPath) -> str:
        raise NotImplementedError()


class DownloadNotFound(APIError):
    status_code = 404
    code = "DOWNLOAD_NOT_FOUND"
    code_verbose = "Download not found"
    default_message = "Download is expired or doesn't exists"


class FileAlreadyDeleted(FilesError):
    status_code = 400
    code = "ALREADY_DELETED"
    code_verbose = "Already deleted"
    default_message = "File '{name}' is already in the Trash"

    def get_message(self, path: StrOrPath) -> str:
        path = Path(path)
        return self.message.format(name=path.name)


class FileAlreadyExists(FilesError):
    status_code = 400
    code = "FILE_ALREADY_EXISTS"
    code_verbose = "File already exists"
    default_message = "The name '{name}' at path {parent} is already taken"

    def get_message(self, path: StrOrPath) -> str:
        path = Path(path)
        return self.message.format(name=path.name, parent=path.parent)


class IsADirectory(FilesError):
    status_code = 400
    code = "IS_A_DIRECTORY"
    code_verbose = "Path is a directory"
    default_message = "Expected the path '{path}' to be a file, but it is a folder"

    def get_message(self, path: StrOrPath) -> str:
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

    def get_message(self, path: StrOrPath) -> str:
        return self.message.format(path=path)


class PathNotFound(FilesError):
    status_code = 404
    code = "PATH_NOT_FOUND"
    code_verbose = "Path not found"
    default_message = "The path '{path}' does not exists"

    def get_message(self, path: StrOrPath) -> str:
        return self.message.format(path=path)


class ThumbnailUnavailable(FilesError):
    status_code = 400
    code = "THUMBNAIL_UNAVAILABLE"
    code_verbose = "Thumbnail unavailable"
    default_message = "Can't generate thumbnail for a file '{name}' at path '{parent}'"

    def get_message(self, path: StrOrPath) -> str:
        path = Path(path)
        return self.message.format(name=path.name, parent=path.parent)
