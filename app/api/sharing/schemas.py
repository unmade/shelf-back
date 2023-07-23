from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Self
from uuid import UUID

from pydantic import BaseModel

from app.app.files.domain import FileMember
from app.app.files.services.file import thumbnails

if TYPE_CHECKING:
    from fastapi import Request

    from app.app.files.domain import File


class FileMemberAccessLevel(str, enum.Enum):
    owner = "owner"
    editor = "editor"
    viewer = "viewer"

    @classmethod
    def from_entity(cls, entity: FileMember) -> FileMemberAccessLevel:
        if entity.owner:
            return cls.owner
        if entity.actions == FileMember.EDITOR:
            return cls.editor
        return cls.viewer


class FileMemberPermissions(BaseModel):
    can_change_access_level: bool = False
    can_remove: bool = False


class FileMemberSchema(BaseModel):
    id: UUID
    file_id: str
    username: str
    display_name: str
    access_level: FileMemberAccessLevel
    permissions: FileMemberPermissions

    @classmethod
    def from_entity(cls, entity: FileMember) -> Self:
        return cls.construct(
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


class SharedLinkFileSchema(BaseModel):
    id: str
    name: str
    size: int
    mtime: float
    mediatype: str
    hidden: bool = False
    thumbnail_url: str | None

    @classmethod
    def from_entity(cls, file: File, token: str, request: Request) -> Self:
        return cls.construct(
            id=file.id,
            name=file.name,
            size=file.size,
            mtime=file.mtime,
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


class CreateSharedLinkResponse(BaseModel):
    token: str


class GetSharedLinkResponse(BaseModel):
    token: str


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


class RemoveMemberRequest(BaseModel):
    file_id: str
    member_id: UUID


class RevokeSharedLinkRequest(BaseModel):
    token: str
    filename: str
