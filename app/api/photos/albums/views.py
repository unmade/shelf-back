from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.api.deps import CurrentUserDeps, UseCasesDeps
from app.api.paginator import Page, get_offset

from .schemas import AlbumSchema, CreateAlbumRequest

router = APIRouter()


@router.post("/create")
async def create_album(
    request: Request,
    payload: CreateAlbumRequest,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> AlbumSchema:
    """Creates a new album."""
    album = await usecases.album.create(title=payload.title, owner_id=user.id)
    return AlbumSchema.from_entity(album, request=request)


@router.get("/list")
async def list_albums(
    request: Request,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=100, le=1000)] = 100,
) -> Page[AlbumSchema]:
    """Lists current user albums."""
    offset = get_offset(page, page_size)
    items = await usecases.album.list_(
        user.id,
        offset=offset,
        limit=page_size,
    )
    return Page(
        page=page,
        items=[AlbumSchema.from_entity(item, request=request) for item in items],
    )
