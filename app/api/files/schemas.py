from __future__ import annotations

from typing import List

from pydantic import BaseModel, validator


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
        return values["name"].startswith(".")


class UploadResult(BaseModel):
    file: File
    updates: List[File]

    class Config:
        orm_mode = True


class CreateFolderResult(File):
    pass


class MoveFolderRequest(BaseModel):
    from_path: str
    to_path: str


class MoveFolderResult(File):
    pass


class ListFolderResult(BaseModel):
    path: str
    items: List[File]
    count: int
