from __future__ import annotations

from enum import Enum
from os.path import normpath
from typing import TYPE_CHECKING, Literal, Self
from uuid import UUID

from pydantic import BaseModel, root_validator, validator

from app import errors, thumbnails
from app.config import TRASH_FOLDER_NAME
from app.domain.entities import ContentMetadata
from app.domain.entities import File as DomainFile

from .exceptions import FileAlreadyDeleted, MalformedPath

if TYPE_CHECKING:
    from fastapi import Request

    from app.entities import File
    from app.tasks import FileTaskResult


class ThumbnailSize(str, Enum):
    xs = "xs"
    sm = "sm"
    md = "md"
    lg = "lg"
    xl = "xl"
    xxl = "2xl"
    xxxl = "3xl"

    def asint(self) -> int:
        """Return integer representation of a size."""
        return _THUMBNAIL_SIZES[self.value]  # type: ignore


_THUMBNAIL_SIZES = {
    ThumbnailSize.xs: 64,
    ThumbnailSize.sm: 128,
    ThumbnailSize.md: 256,
    ThumbnailSize.lg: 512,
    ThumbnailSize.xl: 1024,
    ThumbnailSize.xxl: 2048,
    ThumbnailSize.xxxl: 4096,
}


def _normalize(path: str) -> str:
    path = path.strip()
    symbols = ["..", "~", "/"]
    for symbol in symbols:
        if path.startswith(symbol):
            raise MalformedPath(f"Path should not start with '{symbol}'")
    return normpath(path)


class FileSchema(BaseModel):
    id: UUID
    name: str
    path: str
    size: int
    mtime: float
    mediatype: str
    hidden: bool = False
    thumbnail_url: str | None

    @classmethod
    def from_entity(cls, file: File | DomainFile, request: Request) -> Self:
        return cls.construct(
            id=file.id,  # type: ignore
            name=file.name,
            path=file.path,
            size=file.size,
            mtime=file.mtime,
            mediatype=file.mediatype,
            hidden=file.is_hidden(),
            thumbnail_url=cls._make_thumbnail_url(request, file),
        )

    @staticmethod
    def _make_thumbnail_url(
        request: Request, file: File | DomainFile
    ) -> str | None:
        if thumbnails.is_supported(file.mediatype):
            return request.url_for("get_thumbnail", file_id=file.id)
        return None


class PathParam(BaseModel):
    __root__: str

    _normalize_path = validator("__root__", allow_reuse=True)(_normalize)


class PathRequest(BaseModel):
    path: str

    _normalize_path = validator("path", allow_reuse=True)(_normalize)


class AsyncTaskID(BaseModel):
    async_task_id: UUID


class AsyncTaskStatus(str, Enum):
    pending = "pending"
    completed = "completed"


class AsyncTaskResult(BaseModel):
    file: FileSchema | None
    err_code: errors.ErrorCode | None

    @classmethod
    def from_entity(
        cls,
        entity: FileTaskResult,
        request: Request,
    ) -> AsyncTaskResult:
        return cls.construct(
            file=FileSchema.from_entity(entity.file, request) if entity.file else None,
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
    items: list[list[FileSchema]]
    count: int


class GetBatchRequest(BaseModel):
    ids: list[UUID]


class GetBatchResponse(BaseModel):
    items: list[FileSchema]
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

    @classmethod
    def from_entity(cls, entity: ContentMetadata) -> Self:
        if entity.data is None:
            return cls(file_id=entity.file_id, data=None)
        return cls(
            file_id=entity.file_id,
            data=DataExif(
                type=entity.data.type,
                make=entity.data.make,
                model=entity.data.model,
                fnumber=entity.data.fnumber,
                exposure=entity.data.exposure,
                iso=entity.data.iso,
                dt_original=entity.data.dt_original,
                dt_digitized=entity.data.dt_digitized,
                height=entity.data.height,
                width=entity.data.width,
            ),
        )


class GetDownloadUrlResponse(BaseModel):
    download_url: str


class ListFolderResponse(BaseModel):
    path: str
    items: list[FileSchema]
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


class UploadResponse(BaseModel):
    file: FileSchema
    updates: list[FileSchema]
