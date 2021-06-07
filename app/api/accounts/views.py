from __future__ import annotations

import asyncio

from edgedb import AsyncIOPool
from fastapi import APIRouter, Depends

from app import actions, crud, errors
from app.api import deps
from app.api.paginator import Page, PageParam, PageSizeParam, get_offset
from app.entities import User

from .exceptions import UserAlreadyExists
from .schemas import Account, CreateAccountRequest, UpdateAccountRequest

router = APIRouter()


@router.post("/create", response_model=Account)
async def create(
    payload: CreateAccountRequest,
    db_pool: AsyncIOPool = Depends(deps.db_pool),
    _: User = Depends(deps.superuser),
):
    """Create new account."""
    try:
        return await actions.create_account(
            db_pool,
            payload.username,
            payload.password,
            email=payload.email,
            first_name=payload.first_name,
            last_name=payload.last_name,
        )
    except errors.UserAlreadyExists as exc:
        raise UserAlreadyExists(str(exc)) from exc


@router.get("/get_current", response_model=Account)
async def get_current(
    db_pool: AsyncIOPool = Depends(deps.db_pool),
    user_id: str = Depends(deps.current_user_id),
):
    """Get account information for a current user."""
    # normally, we would re-raised UserNotFound error, but if some user,
    # doesn't have an account, then it is data integrity error, so fail miserably.
    return await crud.account.get(db_pool, user_id)


@router.get("/list_all", response_model=Page[Account])
async def list_all(
    page: int = PageParam,
    per_page: int = PageSizeParam,
    db_pool: AsyncIOPool = Depends(deps.db_pool),
    _: User = Depends(deps.superuser),
):
    """List all accounts."""
    offset = get_offset(page, per_page)
    count, accounts = await asyncio.gather(
        crud.account.count(db_pool),
        crud.account.list_all(db_pool, offset=offset, limit=per_page)
    )
    return Page(
        page=page,
        count=count,
        results=accounts,
    )


@router.patch("/update", response_model=Account)
async def update(
    payload: UpdateAccountRequest,
    db_pool: AsyncIOPool = Depends(deps.db_pool),
    user_id: str = Depends(deps.current_user_id),
):
    """Update account details."""
    return await crud.account.update(db_pool, user_id, payload.as_update())
