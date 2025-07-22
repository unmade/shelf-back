from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.app.infrastructure.database import SENTINEL_ID
from app.app.users.domain import Account, User

if TYPE_CHECKING:
    from app.app.users.repositories import IAccountRepository

pytestmark = [pytest.mark.anyio, pytest.mark.database]


class TestGetByUserID:
    async def test(
        self, user: User, account: Account, account_repo: IAccountRepository
    ):
        retrieved = await account_repo.get_by_user_id(user.id)
        assert retrieved == account

    async def test_when_account_does_not_exist(self, account_repo: IAccountRepository):
        user_id = uuid.uuid4()
        with pytest.raises(User.NotFound):
            await account_repo.get_by_user_id(user_id)


class TestSave:
    async def test(self, user: User, account_repo: IAccountRepository):
        # GIVEN
        account = Account(
            id=SENTINEL_ID,
            user_id=user.id,
            storage_quota=1024**3,
        )
        # WHEN
        created_account = await account_repo.save(account)
        # THEN
        assert created_account.id != SENTINEL_ID
        account.id = created_account.id
        assert created_account == account
