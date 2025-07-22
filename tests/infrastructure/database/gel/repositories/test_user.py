from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from app.app.infrastructure.database import SENTINEL_ID
from app.app.users.domain import User
from app.infrastructure.database.gel.db import db_context

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.users.repositories import IUserRepository
    from app.infrastructure.database.gel.repositories import UserRepository

    from ..conftest import UserFactory

pytestmark = [pytest.mark.anyio, pytest.mark.database]


async def _get_by_id(user_id: UUID) -> User:
    query = """
        SELECT
            User {
                id,
                username,
                password,
                email,
                email_verified,
                display_name,
                created_at,
                last_login_at,
                active,
                superuser,
            }
        FILTER
            .id = <uuid>$user_id
    """
    obj = await db_context.get().query_required_single(query, user_id=user_id)
    return User(
        id=obj.id,
        username=obj.username,
        password=obj.password,
        email=obj.email,
        email_verified=obj.email_verified,
        display_name=obj.display_name,
        created_at=obj.created_at,
        last_login_at=obj.last_login_at,
        active=obj.active,
        superuser=obj.superuser,
    )


class TestExistsWithEmail:
    async def test(self, user_repo: UserRepository, user_factory: UserFactory):
        # GIVEN / WHEN / THEN
        email = "johndoe@example.com"
        result = await user_repo.exists_with_email(email)
        assert result is False

        # GIVEN / WHEN / THEN
        await user_factory(email=email)
        result = await user_repo.exists_with_email(email)
        assert result is True


class TestGet:
    async def test_get_by_id(self, user_repo: UserRepository, user: User):
        retrieved_user = await user_repo.get(id=user.id)
        assert retrieved_user == user

    async def test_by_username(self, user_repo: UserRepository, user: User):
        retrieved_user = await user_repo.get(username=user.username)
        assert retrieved_user == user

    async def test_when_user_does_not_exist(self, user_repo: UserRepository):
        user_id = uuid.uuid4()
        with pytest.raises(User.NotFound):
            await user_repo.get(id=user_id)


class TestSave:
    async def test(self, user_repo: IUserRepository):
        user = User(
            id=SENTINEL_ID,
            username="admin",
            password="psswd",
            email="admin@getshelf.cloud",
            email_verified=False,
            display_name="John Doe",
            active=True,
            created_at=datetime(2024, 2, 4, tzinfo=UTC),
            last_login_at=None,
        )
        created_user = await user_repo.save(user)
        assert created_user.id != SENTINEL_ID
        assert user.username == user.username
        assert user.password == user.password
        assert user.email == "admin@getshelf.cloud"
        assert user.email_verified is False
        assert user.display_name == "John Doe"
        assert user.active is True
        assert user.superuser is False

    async def test_when_user_already_exists(self, user_repo: IUserRepository):
        user = User(
            id=SENTINEL_ID,
            username="admin",
            password="psswd",
            email=None,
            email_verified=False,
            display_name="",
            active=True,
        )
        await user_repo.save(user)

        with pytest.raises(User.AlreadyExists) as excinfo:
            await user_repo.save(user)

        assert str(excinfo.value) == "Username 'admin' is taken"


class TestUpdate:
    async def test(self, user_repo: IUserRepository, user: User):
        # GIVEN
        assert user.email_verified is False
        # WHEN
        result = await user_repo.update(user.id, email_verified=True)
        # THEN
        assert result.email_verified is True
        updated_user = await _get_by_id(user.id)
        assert updated_user.email_verified is True
