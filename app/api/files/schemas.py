from __future__ import annotations

from enum import Enum
from os.path import normpath
from typing import TYPE_CHECKING, Type
from uuid import UUID

from pydantic import BaseModel, root_validator, validator

from app import mediatypes
from app.config import TRASH_FOLDER_NAME

from .exceptions import FileAlreadyDeleted, MalformedPath

if TYPE_CHECKING:
    from app.entities import File as FileEntity


class ThumbnailSize(str, Enum):
    xs = "xs"
    sm = "sm"
    md = "md"
    lg = "lg"
    xl = "xl"

    def asint(self) -> int:
        """Return integer representation of a size."""
        return _THUMBNAIL_SIZES[self.name]  # type: ignore


_THUMBNAIL_SIZES = {
    ThumbnailSize.xs: 64,
    ThumbnailSize.sm: 128,
    ThumbnailSize.md: 258,
    ThumbnailSize.lg: 512,
    ThumbnailSize.xl: 1024,
}


def _normalize(path: str) -> str:
    path = path.strip()
    symbols = ["..", "~", "/"]
    for symbol in symbols:
        if path.startswith(symbol):
            raise MalformedPath(f"Path should not start with '{symbol}'")
    return normpath(path)


class GetDownloadUrlResult(BaseModel):
    download_url: str


class File(BaseModel):
    id: UUID
    name: str
    path: str
    size: int
    mtime: float
    mediatype: str
    hidden: bool = False
    has_thumbnail: bool = False

    @classmethod
    def from_file(cls: Type[File], file: FileEntity) -> File:
        return cls.construct(
            id=file.id,
            name=file.name,
            path=file.path,
            size=file.size,
            mtime=file.mtime,
            mediatype=file.mediatype,
            hidden=file.is_hidden(),
        )

    @validator("hidden", always=True)
    def is_hidden(cls, value, values, config, field):
        return values["name"].startswith(".") or values["name"] == TRASH_FOLDER_NAME

    @validator("has_thumbnail")
    def set_has_thumbnail(cls, value, values, config, field):
        if mediatypes.is_image(values["mediatype"]):
            return True
        return False


class ListFolderResult(BaseModel):
    path: str
    items: list[File]
    count: int


class MoveRequest(BaseModel):
    from_path: str
    to_path: str

    _normalize_path = validator("from_path", "to_path", allow_reuse=True)(_normalize)

    @validator("from_path", "to_path")
    def path_should_not_be_home_or_trash_folders(cls, value: str):
        if value == "." or value.lower() == TRASH_FOLDER_NAME.lower():
            raise MalformedPath("Can't move Home or Trash folder")
        if value.lower().startswith(f"{TRASH_FOLDER_NAME.lower()}/"):
            raise MalformedPath("Can't move files inside Trash")
        return value.strip()

    @root_validator
    def check_path_does_not_contain_itself(cls, values):
        if values["to_path"].lower().startswith(f"{values['from_path'].lower()}/"):
            raise MalformedPath("Destination path should not start with source path")
        return values


class MoveBatchRequest(BaseModel):
    items: list[MoveRequest]


class PathRequest(BaseModel):
    path: str

    _normalize_path = validator("path", allow_reuse=True)(_normalize)


class DeletePathRequest(PathRequest):
    @validator("path")
    def check_path_is_not_special(cls, value: str):
        if value.lower() in (TRASH_FOLDER_NAME.lower(), "."):
            message = f"Path '{value}' is a special path and can't be deleted"
            raise MalformedPath(message)
        return value


class MoveToTrashRequest(PathRequest):
    @validator("path")
    def check_path_is_not_trash(cls, value: str):
        if value.lower() == TRASH_FOLDER_NAME.lower():
            raise MalformedPath("Can't move Trash into itself")
        if value.lower().startswith(f"{TRASH_FOLDER_NAME.lower()}/"):
            raise FileAlreadyDeleted(path=value)
        return value


class UploadResult(BaseModel):
    file: File
    updates: list[File]
