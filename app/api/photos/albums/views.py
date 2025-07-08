from __future__ import annotations

from typing import Annotated, TypeAlias

from fastapi import APIRouter, Path, Query, Request

from app.api.deps import CurrentUserDeps, UseCasesDeps
from app.api.paginator import Page, get_offset
from app.api.photos import exceptions
from app.app.photos.domain import Album

from .schemas import (
    AddAlbumItemsRequest,
    AlbumItemSchema,
    AlbumSchema,
    CreateAlbumRequest,
    RemoveAlbumItemsRequest,
)

router = APIRouter()

AlbumSlugParam: TypeAlias = Annotated[str, Path(min_length=1, max_length=512)]


@router.put("/{slug}/items")
async def add_album_items(
    slug: AlbumSlugParam,
    payload: AddAlbumItemsRequest,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> None:
    """Adds items to the album."""
    await usecases.album.add_album_items(
        user.id,
        slug,
        file_ids=payload.file_ids,
    )


@router.post("")
async def create_album(
    request: Request,
    payload: CreateAlbumRequest,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> AlbumSchema:
    """Creates a new album."""
    album = await usecases.album.create(title=payload.title, owner_id=user.id)
    return AlbumSchema.from_entity(album, request=request)


@router.get("/{slug}")
async def get_album(
    slug: AlbumSlugParam,
    request: Request,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> AlbumSchema:
    """Returns album by its slug."""
    try:
        album = await usecases.album.get_by_slug(user.id, slug)
    except Album.NotFound as exc:
        raise exceptions.AlbumNotFound() from exc
    return AlbumSchema.from_entity(album, request=request)


@router.get("")
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


@router.get("/{slug}/items")
async def list_album_items(
    slug: AlbumSlugParam,
    request: Request,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=100, le=1000)] = 100,
) -> Page[AlbumItemSchema]:
    """Lists media items in the given album."""
    offset = get_offset(page, page_size)
    items = await usecases.album.list_items(
        user.id,
        slug,
        offset=offset,
        limit=page_size,
    )
    return Page(
        page=page,
        items=[AlbumItemSchema.from_entity(item, request=request) for item in items],
    )


@router.delete("/{slug}/items")
async def remove_album_items(
    slug: AlbumSlugParam,
    payload: RemoveAlbumItemsRequest,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> None:
    """Removes items from the album."""
    await usecases.album.remove_album_items(
        user.id,
        slug,
        file_ids=payload.file_ids,
    )
