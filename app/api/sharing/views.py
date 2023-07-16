from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.api import exceptions, shortcuts
from app.api.deps import NamespaceDeps, UseCasesDeps
from app.api.files.exceptions import PathNotFound
from app.api.files.schemas import PathRequest, ThumbnailSize
from app.app.files.domain import File, FileMember, SharedLink, mediatypes
from app.app.users.domain import User

from .exceptions import FileMemberAlreadyExists, SharedLinkNotFound
from .schemas import (
    AddFileMemberRequest,
    CreateSharedLinkResponse,
    FileMemberSchema,
    GetSharedLinkDownloadUrlRequest,
    GetSharedLinkDownloadUrlResponse,
    GetSharedLinkFileRequest,
    GetSharedLinkResponse,
    ListFileMembersRequest,
    ListFileMembersResponse,
    RemoveMemberRequest,
    RevokeSharedLinkRequest,
    SharedLinkFileSchema,
)

router = APIRouter()


@router.post("/add_member")
async def add_member(
    payload: AddFileMemberRequest,
    namespace: NamespaceDeps,
    usecases: UseCasesDeps,
) -> FileMemberSchema:
    """Add a new file member."""
    file_id, username = str(payload.file_id), payload.username

    try:
        member = await usecases.sharing.add_member(namespace.path, file_id, username)
    except File.NotFound as exc:
        raise PathNotFound(path=file_id) from exc
    except FileMember.AlreadyExists as exc:
        raise FileMemberAlreadyExists() from exc
    except User.NotFound as exc:
        raise exceptions.UserNotFound() from exc

    return FileMemberSchema.from_entity(member)


@router.post("/create_shared_link")
async def create_shared_link(
    payload: PathRequest,
    namespace: NamespaceDeps,
    usecases: UseCasesDeps,
) -> CreateSharedLinkResponse:
    """Create a shared link for a file at a given path."""
    ns_path = str(namespace.path)
    try:
        link = await usecases.sharing.create_link(ns_path, payload.path)
    except File.NotFound as exc:
        raise PathNotFound(path=payload.path) from exc

    return CreateSharedLinkResponse(token=link.token)


@router.post("/get_shared_link")
async def get_shared_link(
    payload: PathRequest,
    namespace: NamespaceDeps,
    usecases: UseCasesDeps,
) -> GetSharedLinkResponse:
    """Return shared link for a file at a given path."""
    ns_path = str(namespace.path)
    try:
        link = await usecases.sharing.get_link(ns_path, payload.path)
    except File.NotFound as exc:
        raise SharedLinkNotFound() from exc
    except SharedLink.NotFound as exc:
        raise SharedLinkNotFound() from exc

    return GetSharedLinkResponse(token=link.token)


@router.post("/get_shared_link_download_url")
async def get_shared_link_download_url(
    request: Request,
    payload: GetSharedLinkDownloadUrlRequest,
    usecases: UseCasesDeps,
) -> GetSharedLinkDownloadUrlResponse:
    """Return a link to download a shared link file."""
    try:
        file = await usecases.sharing.get_shared_item(payload.token)
    except SharedLink.NotFound as exc:
        raise SharedLinkNotFound() from exc

    key = await shortcuts.create_download_cache(file.ns_path, file.path)

    download_url = request.url_for("download")
    return GetSharedLinkDownloadUrlResponse(download_url=f"{download_url}?key={key}")


@router.post("/get_shared_link_file")
async def get_shared_link_file(
    request: Request,
    payload: GetSharedLinkFileRequest,
    usecases: UseCasesDeps,
) -> SharedLinkFileSchema:
    """Return a shared link file information."""
    try:
        file = await usecases.sharing.get_shared_item(payload.token)
    except SharedLink.NotFound as exc:
        raise SharedLinkNotFound() from exc

    return SharedLinkFileSchema.from_entity(file, payload.token, request)


@router.get("/get_shared_link_thumbnail/{token}")
async def get_shared_link_thumbnail(
    token: str,
    size: ThumbnailSize,
    usecases: UseCasesDeps,
):
    """Get a thumbnail for a shared link file."""
    try:
        _, thumb = await usecases.sharing.get_link_thumbnail(token, size=size.asint())
    except SharedLink.NotFound as exc:
        raise SharedLinkNotFound() from exc

    filename = f"thumbnail-{size.value}.webp"
    headers = {
        "Content-Disposition": f'inline; filename="{filename}"',
        "Content-Length": str(len(thumb)),
        "Content-Type": mediatypes.IMAGE_WEBP,
        "Cache-Control": "private, max-age=31536000, no-transform",
    }
    return Response(thumb, headers=headers)


@router.post("/list_members")
async def list_members(
    payload: ListFileMembersRequest,
    namespace: NamespaceDeps,
    usecases: UseCasesDeps,
) -> ListFileMembersResponse:
    """List item members at a given path."""
    try:
        members = await usecases.sharing.list_members(namespace.path, str(payload.id))
    except File.NotFound as exc:
        raise PathNotFound(path=str(payload.id)) from exc

    return ListFileMembersResponse(
        members=[
            FileMemberSchema.from_entity(member)
            for member in members
        ]
    )


@router.post("/remove_member")
async def remove_member(
    payload: RemoveMemberRequest,
    _: NamespaceDeps,
    usecases: UseCasesDeps,
) -> None:
    try:
        await usecases.sharing.remove_member(payload.file_id, payload.member_id)
    except File.NotFound as exc:
        raise PathNotFound(path=str(payload.file_id)) from exc


@router.post("/revoke_shared_link")
async def revoke_shared_link(
    payload: RevokeSharedLinkRequest,
    _: NamespaceDeps,
    usecases: UseCasesDeps,
) -> None:
    """Revoke shared link."""
    await usecases.sharing.revoke_link(payload.token)


@router.post("/set_member_access_level")
async def set_member_access_level(
    _: NamespaceDeps,
    usecases: UseCasesDeps,
):
    return {}
