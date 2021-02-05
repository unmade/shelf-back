from __future__ import annotations

from typing import List

from pydantic import BaseModel, validator

from app.config import TRASH_FOLDER_NAME


class FolderPath(BaseModel):
    path: str


class File(BaseModel):
    id: int
    type: str
    name: str
    path: str
    size: int
    mtime: float
    hidden: bool = None

    class Config:
        orm_mode = True

    @validator("hidden", always=True)
    def is_hidden(cls, value, values, config, field):
        return values["name"].startswith(".") or values["name"] == TRASH_FOLDER_NAME


class UploadResult(BaseModel):
    file: File
    updates: List[File]

    class Config:
        orm_mode = True


class MoveFolderRequest(BaseModel):
    from_path: str
    to_path: str


class MoveFolderResult(File):
    pass


class MoveToTrashResult(File):
    pass


class ListFolderResult(BaseModel):
    path: str
    items: List[File]
    count: int
