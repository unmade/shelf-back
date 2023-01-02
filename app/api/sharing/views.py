import secrets

from edgedb import AsyncIOClient
from fastapi import APIRouter, Depends, Request

from app import crud, errors, taskgroups
from app.api import deps, shortcuts
from app.api.files.exceptions import PathNotFound
from app.api.files.schemas import PathRequest, ThumbnailSize
from app.cache import cache
from app.entities import Namespace

from .exceptions import SharedLinkNotFound
from .schemas import (
    CreateSharedLinkResponse,
    GetSharedLinkFileRequest,
    GetSharedLinkDownloadUrlRequest,
    GetSharedLinkDownloadUrlResponse,
    SharedLinkFile,
)

router = APIRouter()


@router.post("/create_shared_link", response_model=CreateSharedLinkResponse)
async def create_shared_link(
    payload: PathRequest,
    db_client: AsyncIOClient = Depends(deps.db_client),
    namespace: Namespace = Depends(deps.namespace),
):
    """Create a shared link for a file in a given path."""
    try:
        file = await crud.file.get(db_client, namespace.path, payload.path)
    except errors.FileNotFound as exc:
        raise PathNotFound(path=payload.path) from exc

    token = secrets.token_urlsafe(16)
    await cache.set(token, value=f"{namespace.path}:{file.path}")
    return CreateSharedLinkResponse(token=token)


@router.post(
    "/get_shared_link_download_url",
    response_model=GetSharedLinkDownloadUrlResponse,
)
async def get_shared_link_download_url(
    request: Request,
    payload: GetSharedLinkDownloadUrlRequest,
    db_client: AsyncIOClient = Depends(deps.db_client),
):
    value = await cache.get(payload.token)
    if not value:
        raise SharedLinkNotFound()

    ns_path, path = value.split(":")
    try:
        file = await crud.file.get(db_client, ns_path, path)
    except errors.FileNotFound as exc:
        raise SharedLinkNotFound() from exc

    key = secrets.token_urlsafe()
    await cache.set(key=key, value=f"{ns_path}:{file.path}", expire=60)

    download_url = request.url_for("download")
    return {"download_url": f"{download_url}?key={key}"}


@router.post("/get_shared_link_file", response_model=SharedLinkFile)
async def get_shared_link_file(
    request: Request,
    payload: GetSharedLinkFileRequest,
    db_client: AsyncIOClient = Depends(deps.db_client),
):
    "Return shared link file information."
    value = await cache.get(payload.token)
    if not value:
        raise SharedLinkNotFound() from None

    ns_path, path = value.split(":")

    try:
        file = await crud.file.get(db_client, ns_path, path)
    except errors.FileNotFound as exc:
        raise SharedLinkNotFound() from exc

    return SharedLinkFile.from_entity(file, request, token=payload.token)


@router.get("/get_shared_link_thumbnail/{token}")
async def get_shared_link_thumbnail(
    token: str,
    size: ThumbnailSize,
    db_client: AsyncIOClient = Depends(deps.db_client),
):
    """Get a thumbnail for a shared link file."""
    value = await cache.get(token)
    if not value:
        raise SharedLinkNotFound() from None

    ns_path, path = value.split(":")
    try:
        namespace, file = await taskgroups.gather(
            crud.namespace.get(db_client, ns_path),
            crud.file.get(db_client, ns_path, path),
        )
    except* errors.FileNotFound as exc:  # noqa: E999
        raise SharedLinkNotFound() from exc

    response = await shortcuts.get_cached_thumbnail(
        db_client,
        namespace,
        file.id,
        size.asint(),
        file.mtime,
    )
    filename = f"thumbnail-{size.value}.webp"
    response.headers["Content-Disposition"] = f'inline; filename="{filename}"'
    return response
