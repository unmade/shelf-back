from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.api import shortcuts
from app.api.deps import NamespaceDeps, UseCasesDeps
from app.api.files.exceptions import PathNotFound
from app.api.files.schemas import PathRequest, ThumbnailSize
from app.app.files.domain import File, SharedLink, mediatypes

from .exceptions import SharedLinkNotFound
from .schemas import (
    CreateSharedLinkResponse,
    GetSharedLinkDownloadUrlRequest,
    GetSharedLinkDownloadUrlResponse,
    GetSharedLinkFileRequest,
    GetSharedLinkResponse,
    RevokeSharedLinkRequest,
    SharedLinkFileSchema,
)

router = APIRouter()


@router.post("/create_shared_link")
async def create_shared_link(
    payload: PathRequest,
    namespace: NamespaceDeps,
    usecases: UseCasesDeps,
) -> CreateSharedLinkResponse:
    """Create a shared link for a file in a given path."""
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
    """Return shared link for a file in a given path."""
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


@router.post("/revoke_shared_link")
async def revoke_shared_link(
    payload: RevokeSharedLinkRequest,
    _: NamespaceDeps,
    usecases: UseCasesDeps,
) -> None:
    """Revoke shared link."""
    await usecases.sharing.revoke_link(payload.token)
