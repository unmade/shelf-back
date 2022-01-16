from __future__ import annotations

from edgedb import AsyncIOPool
from fastapi import APIRouter, Depends

from app import actions, crud, errors
from app.api import deps
from app.entities import Namespace

from . import exceptions, schemas

router = APIRouter()


@router.post("/bookmarks/add")
async def add_bookmark(
    payload: schemas.IDRequest,
    db_pool: AsyncIOPool = Depends(deps.db_pool),
    namespace: Namespace = Depends(deps.namespace),
    user_id: str = Depends(deps.current_user_id),
):
    """Add a file to user bookmarks."""
    try:
        file = await crud.file.get_by_id(db_pool, payload.id)
    except errors.FileNotFound as exc:
        raise exceptions.FileNotFound() from exc

    if not await crud.file.exists(db_pool, namespace.path, file.path):
        raise exceptions.FileNotFound()

    await actions.add_bookmark(db_pool, user_id, file.id)


@router.get("/bookmarks/list", response_model=schemas.ListBookmarksResponse)
async def list_bookmarks(
    db_pool: AsyncIOPool = Depends(deps.db_pool),
    user_id: str = Depends(deps.current_user_id),
):
    """List user bookmarks."""
    return schemas.ListBookmarksResponse(
        items=await crud.user.list_bookmarks(db_pool, user_id),
    )


@router.post("/bookmarks/remove")
async def remove_bookmark(
    payload: schemas.IDRequest,
    db_pool: AsyncIOPool = Depends(deps.db_pool),
    user_id: str = Depends(deps.current_user_id),
):
    """Remove a file from user bookmarks."""
    await actions.remove_bookmark(db_pool, user_id, payload.id)
