from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, Literal, Self, assert_never
from uuid import UUID

from pydantic import BaseModel

from app.app.files.domain import FileMember
from app.app.files.services.thumbnailer import thumbnails

if TYPE_CHECKING:
    from fastapi import Request

    from app.app.files.domain import AnyFile, File, SharedLink
    from app.app.files.domain.file_member import FileMemberActions


class FileMemberAccessLevel(str, enum.Enum):
    owner = "owner"
    editor = "editor"
    viewer = "viewer"

    @classmethod
    def from_entity(cls, entity: FileMember) -> FileMemberAccessLevel:
        if entity.actions == FileMember.OWNER:
            return cls.owner
        if entity.actions == FileMember.EDITOR:
            return cls.editor
        return cls.viewer

    def as_actions(self) -> FileMemberActions:
        match self:
            case FileMemberAccessLevel.editor:
                return FileMember.EDITOR
            case FileMemberAccessLevel.owner:
                raise AssertionError(f"unsupported value: `{self}`")
            case FileMemberAccessLevel.viewer:
                return FileMember.VIEWER
            case _:  # pragma: no cover
                assert_never(self)

class FileMemberPermissions(BaseModel):
    can_change_access_level: bool = False
    can_remove: bool = False


class FileMemberSchema(BaseModel):
    id: UUID
    file_id: UUID
    username: str
    display_name: str
    access_level: FileMemberAccessLevel
    permissions: FileMemberPermissions

    @classmethod
    def from_entity(cls, entity: FileMember) -> Self:
        return cls(
            id=entity.user.id,
            file_id=entity.file_id,
            username=entity.user.username,
            display_name=entity.display_name,
            access_level=FileMemberAccessLevel.from_entity(entity),
            permissions=FileMemberPermissions(
                can_change_access_level=not entity.owner,
                can_remove=not entity.owner,
            ),
        )


class SharedFileSchema(BaseModel):
    id: UUID
    name: str
    path: str
    size: int
    modified_at: datetime
    mediatype: str
    hidden: bool = False
    thumbnail_url: str | None

    @classmethod
    def from_entity(cls, file: AnyFile, request: Request) -> Self:
        return cls(
            id=file.id,
            name=file.name,
            path=str(file.path),
            size=file.size,
            modified_at=file.modified_at,
            mediatype=file.mediatype,
            hidden=file.name.startswith('.'),
            thumbnail_url=cls._make_thumbnail_url(request, file),
        )

    @staticmethod
    def _make_thumbnail_url(request: Request, file: AnyFile) -> str | None:
        if thumbnails.is_supported(file.mediatype):
            return str(request.url_for("get_thumbnail", file_id=file.id))
        return None


class SharedLinkSchema(BaseModel):
    file_id: UUID
    token: str
    created_at: datetime

    @classmethod
    def from_entity(cls, entity: SharedLink) -> Self:
        return cls(
            file_id=entity.file_id,
            token=entity.token,
            created_at=entity.created_at,
        )


class SharedLinkFileSchema(BaseModel):
    id: UUID
    name: str
    size: int
    modified_at: datetime
    mediatype: str
    hidden: bool = False
    thumbnail_url: str | None

    @classmethod
    def from_entity(cls, file: File, token: str, request: Request) -> Self:
        return cls(
            id=file.id,
            name=file.name,
            size=file.size,
            modified_at=file.modified_at,
            mediatype=file.mediatype,
            hidden=file.name.startswith('.'),
            thumbnail_url=cls._make_thumbnail_url(file, token, request),
        )

    @staticmethod
    def _make_thumbnail_url(file: File, token: str, request: Request) -> str | None:
        if thumbnails.is_supported(file.mediatype):
            return str(request.url_for("get_shared_link_thumbnail", token=token))
        return None


class AddFileMemberRequest(BaseModel):
    file_id: UUID
    username: str


class GetSharedLinkDownloadUrlRequest(BaseModel):
    token: str
    filename: str


class GetSharedLinkDownloadUrlResponse(BaseModel):
    download_url: str


class GetSharedLinkFileRequest(BaseModel):
    token: str
    filename: str


class ListFileMembersRequest(BaseModel):
    id: UUID


class ListFileMembersResponse(BaseModel):
    members: list[FileMemberSchema]


class ListFileMembersBatchRequest(BaseModel):
    ids: list[UUID]


class ListFileMemberBatchItem(BaseModel):
    file_id: UUID
    members: list[FileMemberSchema]


class ListFileMembersBatchResponse(BaseModel):
    Item: ClassVar[type[ListFileMemberBatchItem]] = ListFileMemberBatchItem

    items: list[ListFileMemberBatchItem]


class ListSharedFilesResponse(BaseModel):
    items: list[SharedFileSchema]


class ListSharedLinksResponse(BaseModel):
    items: list[SharedLinkSchema]


class RemoveMemberRequest(BaseModel):
    file_id: UUID
    member_id: UUID


class RevokeSharedLinkRequest(BaseModel):
    token: str
    filename: str


class SetMemberAccessLevelRequest(BaseModel):
    file_id: UUID
    member_id: UUID
    access_level: Literal[FileMemberAccessLevel.editor, FileMemberAccessLevel.viewer]
