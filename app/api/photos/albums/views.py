from __future__ import annotations

from typing import Annotated

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
    SetAlbumCoverRequest,
    UpdateAlbumRequest,
)

router = APIRouter()

AlbumSlugParam = Annotated[str, Path(min_length=1, max_length=512)]


@router.put("/{slug}/items")
async def add_album_items(
    request: Request,
    slug: AlbumSlugParam,
    payload: AddAlbumItemsRequest,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> AlbumSchema:
    """Adds items to the album."""
    try:
        album = await usecases.album.add_album_items(
            user.id,
            slug,
            file_ids=payload.file_ids,
        )
    except Album.NotFound as exc:
        raise exceptions.AlbumNotFound() from exc

    return AlbumSchema.from_entity(album, request=request)


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


@router.delete("/{slug}")
async def delete_album(
    request: Request,
    slug: AlbumSlugParam,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> AlbumSchema:
    """Deletes the album."""
    try:
        album = await usecases.album.delete(user.id, slug)
    except Album.NotFound as exc:
        raise exceptions.AlbumNotFound() from exc

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


@router.delete("/{slug}/cover")
async def remove_album_cover(
    request: Request,
    slug: AlbumSlugParam,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> AlbumSchema:
    """Removes album cover."""
    try:
        album = await usecases.album.remove_cover(user.id, slug)
    except Album.NotFound as exc:
        raise exceptions.AlbumNotFound() from exc

    return AlbumSchema.from_entity(album, request=request)


@router.delete("/{slug}/items")
async def remove_album_items(
    request: Request,
    slug: AlbumSlugParam,
    payload: RemoveAlbumItemsRequest,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> AlbumSchema:
    """Removes items from the album."""
    try:
        album = await usecases.album.remove_album_items(
            user.id,
            slug,
            file_ids=payload.file_ids,
        )
    except Album.NotFound as exc:
        raise exceptions.AlbumNotFound() from exc

    return AlbumSchema.from_entity(album, request=request)


@router.put("/{slug}/cover")
async def set_album_cover(
    request: Request,
    slug: AlbumSlugParam,
    payload: SetAlbumCoverRequest,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> AlbumSchema:
    """Sets the album cover."""
    try:
        album = await usecases.album.set_cover(user.id, slug, file_id=payload.file_id)
    except Album.NotFound as exc:
        raise exceptions.AlbumNotFound() from exc

    return AlbumSchema.from_entity(album, request=request)


@router.patch("/{slug}")
async def update_album(
    request: Request,
    slug: AlbumSlugParam,
    payload: UpdateAlbumRequest,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> AlbumSchema:
    """Updates the album."""
    try:
        album = await usecases.album.rename(
            user.id,
            slug,
            new_title=payload.title,
        )
    except Album.NotFound as exc:
        raise exceptions.AlbumNotFound() from exc

    return AlbumSchema.from_entity(album, request=request)
