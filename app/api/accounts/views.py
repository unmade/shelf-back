from __future__ import annotations

from edgedb import AsyncIOClient
from fastapi import APIRouter, Depends

from app import crud, taskgroups
from app.api import deps
from app.api.paginator import Page, PageParam, PageSizeParam, get_offset
from app.entities import User

from .schemas import (
    AccountSchema,
    GetAccountSpaceUsageResponse,
    UpdateAccountRequest,
)

router = APIRouter()


@router.get("/get_current")
async def get_current(
    db_client: AsyncIOClient = Depends(deps.db_client),
    user_id: str = Depends(deps.current_user_id),
) -> AccountSchema:
    """Get account information for a current user."""
    # normally, we would re-raised UserNotFound error, but if some user,
    # doesn't have an account, then it is data integrity error, so fail miserably.
    return AccountSchema.from_entity(
        await crud.account.get(db_client, user_id)
    )


@router.get("/get_space_usage")
async def get_space_usage(
    db_client: AsyncIOClient = Depends(deps.db_client),
    user_id: str = Depends(deps.current_user_id),
) -> GetAccountSpaceUsageResponse:
    """Get the space usage information for the current account."""
    used, quota = await crud.account.get_space_usage(db_client, user_id)
    return GetAccountSpaceUsageResponse(used=used, quota=quota)


@router.get("/list_all")
async def list_all(
    page: int = PageParam,
    per_page: int = PageSizeParam,
    db_client: AsyncIOClient = Depends(deps.db_client),
    _: User = Depends(deps.superuser),
) -> Page[AccountSchema]:
    """List all accounts."""
    offset = get_offset(page, per_page)
    count, accounts = await taskgroups.gather(
        crud.account.count(db_client),
        crud.account.list_all(db_client, offset=offset, limit=per_page)
    )
    return Page(
        page=page,
        count=count,
        results=[AccountSchema.from_entity(account) for account in accounts],
    )


@router.patch("/update")
async def update(
    payload: UpdateAccountRequest,
    db_client: AsyncIOClient = Depends(deps.db_client),
    user_id: str = Depends(deps.current_user_id),
) -> AccountSchema:
    """Update account details."""
    return AccountSchema.from_entity(
        await crud.account.update(db_client, user_id, payload.as_update())
    )
