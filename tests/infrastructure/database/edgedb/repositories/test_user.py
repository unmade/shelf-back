from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app import errors
from app.domain.entities import SENTINEL_ID, User

if TYPE_CHECKING:
    from app.app.repositories import IUserRepository

pytestmark = [pytest.mark.asyncio]


class TestSave:
    async def test(self, user_repo: IUserRepository):
        user = User(id=SENTINEL_ID, username="admin", password="psswd")
        created_user = await user_repo.save(user)
        assert created_user.id != SENTINEL_ID
        assert user.username == user.username
        assert user.password == user.password
        assert user.superuser is False

    async def test_when_user_already_exists(self, user_repo: IUserRepository):
        user = User(id=SENTINEL_ID, username="admin", password="psswd")
        await user_repo.save(user)

        with pytest.raises(errors.UserAlreadyExists) as excinfo:
            await user_repo.save(user)

        assert str(excinfo.value) == "Username 'admin' is taken"
