from __future__ import annotations

from typing import List

from pydantic import BaseModel, validator

from app.config import TRASH_FOLDER_NAME

from .exceptions import InvalidPath


def _normalize(path: str) -> str:
    symbols = ["..", "~", "/"]
    for symbol in symbols:
        if path.startswith(symbol):
            raise InvalidPath(f"Path should not start with '{symbol}'")
    return path.strip()


class GetDownloadUrlResult(BaseModel):
    download_url: str


class File(BaseModel):
    id: int
    name: str
    path: str
    size: int
    mtime: float
    type: str = None
    hidden: bool = None

    class Config:
        orm_mode = True

    def get_type(cls, value, values, config, field) -> str:
        return "folder" if values["is_dir"] else "file"

    @validator("hidden", always=True)
    def is_hidden(cls, value, values, config, field):
        return values["name"].startswith(".") or values["name"] == TRASH_FOLDER_NAME


class ListFolderResult(BaseModel):
    path: str
    items: List[File]
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


class PathRequest(BaseModel):
    path: str

    _normalize_path = validator("path", allow_reuse=True)(_normalize)


class UploadResult(BaseModel):
    file: File
    updates: List[File]
