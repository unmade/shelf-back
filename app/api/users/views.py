from __future__ import annotations

from edgedb import AsyncIOClient
from fastapi import APIRouter, Depends

from app import actions, crud, errors
from app.api import deps
from app.entities import Namespace

from . import exceptions
from .schemas import IDRequest, ListBookmarksResponse

router = APIRouter()


@router.post("/bookmarks/add")
async def add_bookmark(
    payload: IDRequest,
    db_client: AsyncIOClient = Depends(deps.db_client),
    namespace: Namespace = Depends(deps.namespace),
    user_id: str = Depends(deps.current_user_id),
) -> None:
    """Add a file to user bookmarks."""
    try:
        file = await crud.file.get_by_id(db_client, payload.id)
    except errors.FileNotFound as exc:
        raise exceptions.FileNotFound() from exc

    if not await crud.file.exists(db_client, namespace.path, file.path):
        raise exceptions.FileNotFound()

    await actions.add_bookmark(db_client, user_id, file.id)


@router.get("/bookmarks/list")
async def list_bookmarks(
    db_client: AsyncIOClient = Depends(deps.db_client),
    user_id: str = Depends(deps.current_user_id),
) -> ListBookmarksResponse:
    """List user bookmarks."""
    return ListBookmarksResponse(
        items=await crud.user.list_bookmarks(db_client, user_id),
    )


@router.post("/bookmarks/remove")
async def remove_bookmark(
    payload: IDRequest,
    db_client: AsyncIOClient = Depends(deps.db_client),
    user_id: str = Depends(deps.current_user_id),
) -> None:
    """Remove a file from user bookmarks."""
    await actions.remove_bookmark(db_client, user_id, payload.id)
