from __future__ import annotations

from edgedb import AsyncIOClient
from fastapi import APIRouter, Depends

from app import actions, crud, errors, taskgroups
from app.api import deps
from app.api.paginator import Page, PageParam, PageSizeParam, get_offset
from app.entities import User

from .exceptions import UserAlreadyExists
from .schemas import (
    Account,
    AccountSpaceUsage,
    CreateAccountRequest,
    UpdateAccountRequest,
)

router = APIRouter()


@router.post("/create", response_model=Account)
async def create(
    payload: CreateAccountRequest,
    db_client: AsyncIOClient = Depends(deps.db_client),
    _: User = Depends(deps.superuser),
):
    """Create new account."""
    try:
        return Account.from_entity(
            await actions.create_account(
                db_client,
                payload.username,
                payload.password,
                email=payload.email,
                first_name=payload.first_name,
                last_name=payload.last_name,
            )
        )
    except errors.UserAlreadyExists as exc:
        raise UserAlreadyExists(str(exc)) from exc


@router.get("/get_current", response_model=Account)
async def get_current(
    db_client: AsyncIOClient = Depends(deps.db_client),
    user_id: str = Depends(deps.current_user_id),
):
    """Get account information for a current user."""
    # normally, we would re-raised UserNotFound error, but if some user,
    # doesn't have an account, then it is data integrity error, so fail miserably.
    return Account.from_entity(
        await crud.account.get(db_client, user_id)
    )


@router.get("/get_space_usage", response_model=AccountSpaceUsage)
async def get_space_usage(
    db_client: AsyncIOClient = Depends(deps.db_client),
    user_id: str = Depends(deps.current_user_id),
):
    """Get the space usage information for the current account."""
    used, quota = await crud.account.get_space_usage(db_client, user_id)
    return AccountSpaceUsage(used=used, quota=quota)


@router.get("/list_all", response_model=Page[Account])
async def list_all(
    page: int = PageParam,
    per_page: int = PageSizeParam,
    db_client: AsyncIOClient = Depends(deps.db_client),
    _: User = Depends(deps.superuser),
):
    """List all accounts."""
    offset = get_offset(page, per_page)
    count, accounts = await taskgroups.gather(
        crud.account.count(db_client),
        crud.account.list_all(db_client, offset=offset, limit=per_page)
    )
    return Page(
        page=page,
        count=count,
        results=[Account.from_entity(account) for account in accounts],
    )


@router.patch("/update", response_model=Account)
async def update(
    payload: UpdateAccountRequest,
    db_client: AsyncIOClient = Depends(deps.db_client),
    user_id: str = Depends(deps.current_user_id),
):
    """Update account details."""
    return Account.from_entity(
        await crud.account.update(db_client, user_id, payload.as_update())
    )
