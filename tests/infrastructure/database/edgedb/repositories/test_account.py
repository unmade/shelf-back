from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import pytest
from dateutil import tz

from app import errors
from app.domain.entities import SENTINEL_ID, Account, User

if TYPE_CHECKING:
    from app.app.repositories import IAccountRepository

pytestmark = [pytest.mark.asyncio]


class TestGetByUserID:
    async def test(
        self, user: User, account: Account, account_repo: IAccountRepository
    ):
        retrieved = await account_repo.get_by_user_id(user.id)
        assert retrieved == account

    async def test_when_account_does_not_exist(self, account_repo: IAccountRepository):
        user_id = uuid.uuid4()
        with pytest.raises(errors.UserNotFound):
            await account_repo.get_by_user_id(user_id)


class TestSave:
    async def test(self, user: User, account_repo: IAccountRepository):
        created_at = datetime(2022, 8, 14, 16, 13, tzinfo=tz.gettz("America/New_York"))
        account = Account(
            id=SENTINEL_ID,
            username=user.username,
            first_name="John",
            last_name="Doe",
            storage_quota=1024**3,
            created_at=created_at,
        )
        created_account = await account_repo.save(account)
        assert created_account.id != SENTINEL_ID
        assert created_account.dict(exclude={"id"}) == account.dict(exclude={"id"})

    async def test_when_email_is_taken(
        self, user: User, account_repo: IAccountRepository
    ):
        account = Account(
            id=SENTINEL_ID,
            username=user.username,
            email="johndoe@example.com",
            first_name="John",
            last_name="Doe",
        )
        await account_repo.save(account)
        with pytest.raises(errors.UserAlreadyExists) as excinfo:
            await account_repo.save(account)
        assert str(excinfo.value) == "Email 'johndoe@example.com' is taken"
