from __future__ import annotations

from enum import Enum
from os.path import normpath
from typing import TYPE_CHECKING, Literal, Type
from uuid import UUID

from pydantic import BaseModel, root_validator, validator

from app import errors, mediatypes
from app.config import TRASH_FOLDER_NAME

from .exceptions import FileAlreadyDeleted, MalformedPath

if TYPE_CHECKING:
    from app import entities


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
    def from_entity(cls: Type[File], file: entities.File) -> File:
        return cls.construct(
            id=file.id,  # type: ignore
            name=file.name,
            path=file.path,
            size=file.size,
            mtime=file.mtime,
            mediatype=file.mediatype,
            hidden=file.is_hidden(),
            has_thumbnail=mediatypes.is_image(file.mediatype),
        )

    @validator("hidden", always=True)
    def is_hidden(cls, value, values, config, field):
        return values["name"].startswith(".") or values["name"] == TRASH_FOLDER_NAME

    @validator("has_thumbnail", always=True)
    def set_has_thumbnail(cls, value, values, config, field):
        return mediatypes.is_image(values["mediatype"])


class PathRequest(BaseModel):
    path: str

    _normalize_path = validator("path", allow_reuse=True)(_normalize)


class AsyncTaskID(BaseModel):
    async_task_id: UUID


class AsyncTaskStatus(str, Enum):
    pending = "pending"
    completed = "completed"


class AsyncTaskResult(BaseModel):
    file: File | None
    err_code: errors.ErrorCode | None

    @classmethod
    def from_entity(cls, entity: entities.FileTaskResult) -> AsyncTaskResult:
        return cls.construct(
            file=File.from_entity(entity.file) if entity.file else None,
            err_code=entity.err_code if entity.err_code else None,
        )


class DeleteImmediatelyRequest(PathRequest):
    @validator("path")
    def check_path_is_not_special(cls, value: str):
        if value.lower() in (TRASH_FOLDER_NAME.lower(), "."):
            message = f"Path '{value}' is a special path and can't be deleted"
            raise MalformedPath(message)
        return value


class DeleteImmediatelyBatchRequest(BaseModel):
    items: list[DeleteImmediatelyRequest]


class DeleteImmediatelyBatchCheckResponse(BaseModel):
    status: AsyncTaskStatus
    result: list[AsyncTaskResult] | None = None


class EmptyTrashCheckResponse(BaseModel):
    status: AsyncTaskStatus
    result: None = None


class FindDuplicatesRequest(PathRequest):
    max_distance: int = 5


class FindDuplicatesResponse(BaseModel):
    path: str
    items: list[list[File]]
    count: int


class GetBatchRequest(BaseModel):
    ids: list[UUID]


class GetBatchResult(BaseModel):
    items: list[File]
    count: int


class DataExif(BaseModel):
    type: Literal["exif"] = "exif"
    make: str | None = None
    model: str | None = None
    fnumber: str | None = None
    exposure: str | None = None
    iso: str | None = None
    dt_original: float | None = None
    dt_digitized: float | None = None
    height: int | None = None
    width: int | None = None


class GetContentMetadataResponse(BaseModel):
    file_id: str
    data: DataExif | None


class GetDownloadUrlResult(BaseModel):
    download_url: str


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
        return value.strip()

    @validator("to_path")
    def to_path_should_not_be_inside_trash_folder(cls, value: str):
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


class MoveBatchCheckResponse(BaseModel):
    status: AsyncTaskStatus
    result: list[AsyncTaskResult] | None = None


class MoveToTrashRequest(PathRequest):
    @validator("path")
    def check_path_is_not_trash(cls, value: str):
        if value.lower() == TRASH_FOLDER_NAME.lower():
            raise MalformedPath("Can't move Trash into itself")
        if value.lower().startswith(f"{TRASH_FOLDER_NAME.lower()}/"):
            raise FileAlreadyDeleted(path=value)
        return value


class MoveToTrashBatchRequest(BaseModel):
    items: list[MoveToTrashRequest]


class UploadResult(BaseModel):
    file: File
    updates: list[File]
