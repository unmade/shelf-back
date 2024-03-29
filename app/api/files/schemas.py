from __future__ import annotations

import enum
from datetime import datetime
from os.path import normpath
from typing import TYPE_CHECKING, Annotated, Literal, Self
from uuid import UUID

from fastapi import UploadFile
from pydantic import BaseModel, RootModel, field_validator, model_validator
from pydantic.functional_validators import AfterValidator

from app.app.files.services.thumbnailer import thumbnails
from app.config import ThumbnailSize as AppThumbnailSize
from app.toolkit import timezone
from app.worker.jobs.files import ErrorCode as TaskErrorCode

from .exceptions import FileAlreadyDeleted, MalformedPath

if TYPE_CHECKING:
    from fastapi import Request

    from app.app.files.domain import AnyFile, ContentMetadata
    from app.worker.jobs.files import FileTaskResult


class ThumbnailSize(enum.StrEnum):
    xs = enum.auto()
    lg = enum.auto()
    xxl = enum.auto()

    def asint(self) -> int:
        """Return integer representation of a size."""
        return _THUMBNAIL_SIZES[self.value]  # type: ignore


_THUMBNAIL_SIZES = {
    ThumbnailSize.xs: AppThumbnailSize.xs,
    ThumbnailSize.lg: AppThumbnailSize.lg,
    ThumbnailSize.xxl: AppThumbnailSize.xxl,
}


def _check_timestamp_less_than_now(value: float) -> float:
    assert value <= timezone.now().timestamp(), (
        "`mtime` can't be greater than current datetime."
    )
    assert value >= timezone.EPOCH.timestamp(), (
        "`mtime` can't be lesser than epoch"
    )
    return value


def _normalize(path: str) -> str:
    if not path.strip():
        raise MalformedPath("Path should not be empty")
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
    mediatype: str
    hidden: bool = False
    shared: bool
    thumbnail_url: str | None
    modified_at: datetime

    @classmethod
    def from_entity(cls, file: AnyFile, request: Request) -> Self:
        return cls(
            id=file.id,
            name=file.name,
            path=str(file.path),
            size=file.size,
            mediatype=file.mediatype,
            hidden=file.is_hidden(),
            shared=file.shared,
            thumbnail_url=cls._make_thumbnail_url(request, file),
            modified_at=file.modified_at,
        )

    @staticmethod
    def _make_thumbnail_url(request: Request, file: AnyFile) -> str | None:
        if thumbnails.is_supported(file.mediatype):
            return str(request.url_for("get_thumbnail", file_id=file.id))
        return None


class LastModifiedParam(RootModel[float]):
    root: Annotated[float, AfterValidator(_check_timestamp_less_than_now)]


class PathParam(RootModel[str]):
    root: Annotated[str, AfterValidator(_normalize)]


class PathRequest(BaseModel):
    path: Annotated[str, AfterValidator(_normalize)]


class IDRequest(BaseModel):
    id: UUID


class AsyncTaskID(BaseModel):
    async_task_id: str


class AsyncTaskStatus(enum.StrEnum):
    pending = enum.auto()
    completed = enum.auto()


class AsyncTaskResult(BaseModel):
    file: FileSchema | None
    err_code: TaskErrorCode | None

    @classmethod
    def from_entity(
        cls,
        entity: FileTaskResult,
        request: Request,
    ) -> AsyncTaskResult:
        return cls(
            file=FileSchema.from_entity(entity.file, request) if entity.file else None,
            err_code=entity.err_code if entity.err_code else None,
        )


class CreateFolderRequest(PathRequest):
    @field_validator("path")
    @classmethod
    def check_path_is_not_special(cls, value: str):
        if value.casefold() in {".", "trash"}:
            message = f"Path '{value}' is a special path and can't be created"
            raise MalformedPath(message)
        if value.casefold().startswith("trash/"):
            message = "Can't create folders in the Trash"
            raise MalformedPath(message)
        return value


class DeleteImmediatelyRequest(PathRequest):
    @field_validator("path")
    @classmethod
    def check_path_is_not_special(cls, value: str):
        if value.casefold() in {".", "trash"}:
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
    focal_length: int | None = None
    focal_length_35mm: int | None = None
    fnumber: str | None = None
    exposure: str | None = None
    iso: str | None = None
    dt_original: float | None = None
    dt_digitized: float | None = None
    height: int | None = None
    width: int | None = None


class GetContentMetadataResponse(BaseModel):
    file_id: UUID
    data: DataExif

    @classmethod
    def from_entity(cls, entity: ContentMetadata) -> Self:
        return cls(
            file_id=entity.file_id,
            data=DataExif(
                type=entity.data.type,
                make=entity.data.make,
                model=entity.data.model,
                focal_length=entity.data.focal_length,
                focal_length_35mm=entity.data.focal_length_35mm,
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
    from_path: Annotated[str, AfterValidator(_normalize)]
    to_path: Annotated[str, AfterValidator(_normalize)]

    @field_validator("from_path", "to_path")
    @classmethod
    def path_should_not_be_home_or_trash_folders(cls, value: str):
        if value == "." or value.casefold() == "trash":
            raise MalformedPath("Can't move Home or Trash folder")
        return value

    @field_validator("to_path")
    @classmethod
    def to_path_should_not_be_inside_trash_folder(cls, value: str):
        if value.casefold().startswith("trash/"):
            raise MalformedPath("Can't move files inside Trash")
        return value

    @model_validator(mode='after')
    def check_path_does_not_contain_itself(self):
        if self.to_path.lower().startswith(f"{self.from_path.lower()}/"):
            raise MalformedPath("'to_path' should not start with 'from_path'")
        return self


class MoveBatchRequest(BaseModel):
    items: list[MoveRequest]


class MoveBatchCheckResponse(BaseModel):
    status: AsyncTaskStatus
    result: list[AsyncTaskResult] | None = None


class MoveToTrashRequest(PathRequest):
    @field_validator("path")
    @classmethod
    def check_path_is_not_trash(cls, value: str):
        if value.casefold() == "trash":
            raise MalformedPath("Can't move Trash into itself")
        if value.casefold().startswith("trash/"):
            raise FileAlreadyDeleted(path=value)
        return value


class MoveToTrashBatchRequest(BaseModel):
    items: list[MoveToTrashRequest]


class UploadContent(UploadFile):
    # UploadFile has size annotated as optional, but in our case it'll always be set
    # So to not bother with mypy and checking for None just override annotation
    size: int


class UploadResponse(BaseModel):
    file: FileSchema
    updates: list[FileSchema]
