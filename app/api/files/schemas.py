from __future__ import annotations

from typing import List

from pydantic import BaseModel


class FolderPath(BaseModel):
    path: str


class File(BaseModel):
    id: int
    type: str
    name: str
    path: str
    size: int
    mtime: float

    class Config:
        orm_mode = True


class UploadResult(File):
    pass


class ListFolderResult(BaseModel):
    path: str
    items: List[File]
    count: int
