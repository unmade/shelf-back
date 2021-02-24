from __future__ import annotations

from typing import TYPE_CHECKING, Type, TypeVar
from uuid import UUID

from pydantic import BaseModel, root_validator, validator

from app.config import TRASH_FOLDER_NAME

from .exceptions import InvalidPath

if TYPE_CHECKING:
    from app.entities import File as FileEntity

T = TypeVar("T", bound="File")


def _normalize(path: str) -> str:
    symbols = ["..", "~", "/"]
    for symbol in symbols:
        if path.startswith(symbol):
            raise InvalidPath(f"Path should not start with '{symbol}'")
    path = path.strip()
    if path.startswith("./"):
        return path[2:]
    return path


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

    @classmethod
    def from_file(cls: Type[T], file: FileEntity) -> T:
        return cls.construct(
            id=file.id,
            name=file.name,
            path=file.path,
            size=file.size,
            mtime=file.mtime,
            mediatype=file.mediatype,
            hidden=file.name.startswith(".") or file.name == TRASH_FOLDER_NAME
        )

    @validator("hidden", always=True)
    def is_hidden(cls, value, values, config, field):
        return values["name"].startswith(".") or values["name"] == TRASH_FOLDER_NAME


class ListFolderResult(BaseModel):
    path: str
    items: list[File]
    count: int


class MoveFolderRequest(BaseModel):
    from_path: str
    to_path: str

    _normalize_path = validator("from_path", "to_path", allow_reuse=True)(_normalize)

    @validator("from_path", "to_path")
    def path_should_not_be_home_or_trash_folders(cls, value: str):
        if value == "." or value == TRASH_FOLDER_NAME:
            raise InvalidPath("should not be Home or Trash folder.")
        if value.startswith(f"{TRASH_FOLDER_NAME}/"):
            raise InvalidPath("should not be path located in Trash folder.")
        return value.strip()

    @root_validator
    def check_path_does_not_contain_itself(cls, values):
        if values["to_path"].startswith(values["from_path"]):
            raise InvalidPath("destination path should not starts with source path.")
        return values


class PathRequest(BaseModel):
    path: str

    _normalize_path = validator("path", allow_reuse=True)(_normalize)


class UploadResult(BaseModel):
    file: File
    updates: list[File]
