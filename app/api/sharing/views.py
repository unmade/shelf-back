from __future__ import annotations

from edgedb import AsyncIOClient
from fastapi import APIRouter, Depends, Request, Response

from app import actions, crud, errors, mediatypes
from app.api import deps, shortcuts
from app.api.files.exceptions import PathNotFound
from app.api.files.schemas import PathRequest, ThumbnailSize
from app.entities import Namespace

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
    db_client: AsyncIOClient = Depends(deps.db_client),
    namespace: Namespace = Depends(deps.namespace),
) -> CreateSharedLinkResponse:
    """Create a shared link for a file in a given path."""
    try:
        link = await actions.get_or_create_shared_link(
            db_client,
            namespace=namespace,
            path=payload.path,
        )
    except errors.FileNotFound as exc:
        raise PathNotFound(path=payload.path) from exc

    return CreateSharedLinkResponse(token=link.token)


@router.post("/get_shared_link")
async def get_shared_link(
    payload: PathRequest,
    db_client: AsyncIOClient = Depends(deps.db_client),
    namespace: Namespace = Depends(deps.namespace),
) -> GetSharedLinkResponse:
    """Return shared link for a file in a given path."""
    try:
        link = await crud.shared_link.get(db_client, namespace.path, payload.path)
    except errors.SharedLinkNotFound as exc:
        raise SharedLinkNotFound() from exc

    return GetSharedLinkResponse(token=link.token)


@router.post("/get_shared_link_download_url")
async def get_shared_link_download_url(
    request: Request,
    payload: GetSharedLinkDownloadUrlRequest,
    db_client: AsyncIOClient = Depends(deps.db_client),
) -> GetSharedLinkDownloadUrlResponse:
    """Return a link to download a shared link file."""
    try:
        link = await crud.shared_link.get_by_token(db_client, token=payload.token)
    except errors.SharedLinkNotFound as exc:
        raise SharedLinkNotFound() from exc

    file = link.file
    key = await shortcuts.create_download_cache(file.namespace.path, file.path)

    download_url = request.url_for("download")
    return GetSharedLinkDownloadUrlResponse(download_url=f"{download_url}?key={key}")


@router.post("/get_shared_link_file")
async def get_shared_link_file(
    request: Request,
    payload: GetSharedLinkFileRequest,
    db_client: AsyncIOClient = Depends(deps.db_client),
) -> SharedLinkFileSchema:
    """Return a shared link file information."""
    try:
        link = await crud.shared_link.get_by_token(db_client, token=payload.token)
    except errors.SharedLinkNotFound as exc:
        raise SharedLinkNotFound() from exc

    return SharedLinkFileSchema.from_entity(link, request)


@router.get("/get_shared_link_thumbnail/{token}")
async def get_shared_link_thumbnail(
    token: str,
    size: ThumbnailSize,
    db_client: AsyncIOClient = Depends(deps.db_client),
):
    """Get a thumbnail for a shared link file."""
    try:
        link = await crud.shared_link.get_by_token(db_client, token=token)
    except errors.SharedLinkNotFound as exc:
        raise SharedLinkNotFound() from exc

    _, thumbnail = await shortcuts.get_cached_thumbnail(
        db_client,
        link.file.namespace,
        link.file.id,
        size=size.asint(),
        mtime=link.file.mtime,
    )

    filename = f"thumbnail-{size.value}.webp"
    headers = {
        "Content-Disposition": f'inline; filename="{filename}"',
        "Content-Length": str(len(thumbnail)),
        "Content-Type": mediatypes.IMAGE_WEBP,
        "Cache-Control": "private, max-age=31536000, no-transform",
    }
    return Response(thumbnail, headers=headers)


@router.post("/revoke_shared_link")
async def revoke_shared_link(
    payload: RevokeSharedLinkRequest,
    _: Namespace = Depends(deps.namespace),
    db_client: AsyncIOClient = Depends(deps.db_client),
) -> None:
    """Revoke shared link."""
    await actions.revoke_shared_link(db_client, payload.token)
