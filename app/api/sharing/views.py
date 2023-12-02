from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.api import exceptions, shortcuts
from app.api.deps import CurrentUserDeps, NamespaceDeps, UseCasesDeps
from app.api.files.exceptions import FileActionNotAllowed, PathNotFound
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
    ListFileMembersBatchRequest,
    ListFileMembersBatchResponse,
    ListFileMembersRequest,
    ListFileMembersResponse,
    ListSharedFilesResponse,
    ListSharedLinksResponse,
    RemoveMemberRequest,
    RevokeSharedLinkRequest,
    SetMemberAccessLevelRequest,
    SharedFileSchema,
    SharedLinkFileSchema,
    SharedLinkSchema,
)

router = APIRouter()


@router.post("/add_member")
async def add_member(
    payload: AddFileMemberRequest,
    namespace: NamespaceDeps,
    usecases: UseCasesDeps,
) -> FileMemberSchema:
    """Add a new file member."""
    file_id, username = payload.file_id, payload.username

    try:
        member = await usecases.sharing.add_member(namespace.path, file_id, username)
    except File.ActionNotAllowed as exc:
        raise FileActionNotAllowed() from exc
    except File.NotFound as exc:
        raise PathNotFound(path=str(file_id)) from exc
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

    key = await shortcuts.create_download_cache(file)

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
    """List members of a file with a given ID."""
    try:
        members = await usecases.sharing.list_members(namespace.path, payload.id)
    except File.ActionNotAllowed as exc:
        raise FileActionNotAllowed() from exc
    except File.NotFound as exc:
        raise PathNotFound(path=str(payload.id)) from exc

    return ListFileMembersResponse(
        members=[
            FileMemberSchema.from_entity(member)
            for member in members
        ]
    )


@router.post("/list_members_batch")
async def list_members_batch(
    payload: ListFileMembersBatchRequest,
    namespace: NamespaceDeps,
    usecases: UseCasesDeps,
) -> ListFileMembersBatchResponse:
    """List members of multiple files at once."""
    result = await usecases.sharing.list_members_batch(namespace.path, payload.ids)
    return ListFileMembersBatchResponse(
        items=[
            ListFileMembersBatchResponse.Item(
                file_id=file_id,
                members=[
                    FileMemberSchema.from_entity(member)
                    for member in members
                ],
            )
            for file_id, members in result.items()
        ]
    )


@router.get("/list_shared_files")
async def list_shared_files(
    request: Request,
    namespace: NamespaceDeps,
    user: CurrentUserDeps,
    usecases: UseCasesDeps,
) -> ListSharedFilesResponse:
    """List recent files shared with a given user including the ones user owns."""
    files = await usecases.sharing.list_shared_files(namespace.path, user.id)
    return ListSharedFilesResponse(
        items=[
            SharedFileSchema.from_entity(file, request)
            for file in files
        ]
    )


@router.get("/list_shared_links")
async def list_shared_links(
    namespace: NamespaceDeps,
    usecases: UseCasesDeps,
) -> ListSharedLinksResponse:
    """List recent shared links."""
    links = await usecases.sharing.list_shared_links(namespace.path)
    return ListSharedLinksResponse(
        items=[
            SharedLinkSchema(
                file_id=link.file_id,
                token=link.token,
            )
            for link in links
        ]
    )


@router.post("/remove_member")
async def remove_member(
    payload: RemoveMemberRequest,
    namespace: NamespaceDeps,
    usecases: UseCasesDeps,
) -> None:
    """Remove a file member."""
    file_id, member_id = payload.file_id, payload.member_id
    try:
        await usecases.sharing.remove_member(namespace.path, file_id, member_id)
    except File.ActionNotAllowed as exc:
        raise FileActionNotAllowed() from exc
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
    payload: SetMemberAccessLevelRequest,
    namespace: NamespaceDeps,
    usecases: UseCasesDeps,
) -> None:
    """Set file member access level."""
    try:
        await usecases.sharing.set_member_actions(
            namespace.path,
            payload.file_id,
            payload.member_id,
            actions=payload.access_level.as_actions(),
        )
    except File.ActionNotAllowed as exc:
        raise FileActionNotAllowed() from exc
    except File.NotFound as exc:
        raise PathNotFound(path=str(payload.file_id)) from exc
