from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.app.infrastructure.database import SENTINEL_ID
from app.app.users.domain import User

if TYPE_CHECKING:
    from app.app.users.repositories import IUserRepository
    from app.infrastructure.database.edgedb.repositories import UserRepository

pytestmark = [pytest.mark.anyio, pytest.mark.database]


class TestGetByID:
    async def test(self, user: User, user_repo: UserRepository):
        retrieved_user = await user_repo.get_by_id(user.id)
        assert retrieved_user == user

    async def test_when_user_does_not_exist(self, user_repo: UserRepository):
        user_id = uuid.uuid4()
        with pytest.raises(User.NotFound):
            await user_repo.get_by_id(user_id)


class TestGetByUsername:
    async def test(self, user: User, user_repo: UserRepository):
        retrieved_user = await user_repo.get_by_username(user.username)
        assert retrieved_user == user

    async def test_when_user_does_not_exist(self, user_repo: UserRepository):
        username = "admin"
        with pytest.raises(User.NotFound):
            await user_repo.get_by_username(username)


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

        with pytest.raises(User.AlreadyExists) as excinfo:
            await user_repo.save(user)

        assert str(excinfo.value) == "Username 'admin' is taken"
