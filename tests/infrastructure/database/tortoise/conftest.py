from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from faker import Faker

from app.app.infrastructure.database import SENTINEL_ID
from app.app.users.domain import User

if TYPE_CHECKING:
    from typing import Protocol

    from app.app.users.repositories import IUserRepository
    from app.infrastructure.database.tortoise import TortoiseDatabase
    from app.infrastructure.database.tortoise.repositories import UserRepository

    class UserFactory(Protocol):
        async def __call__(
            self,
            username: str | None = None,
            password: str | None = None,
            email: str | None = None,
        ) -> User:
            ...

fake = Faker()


@pytest.fixture
def user_repo(tortoise_database: TortoiseDatabase) -> UserRepository:
    return tortoise_database.user


@pytest.fixture
def user_factory(user_repo: IUserRepository) -> UserFactory:
    async def factory(
        username: str | None = None,
        password: str | None = None,
        email: str | None = None,
    ) -> User:
        return await user_repo.save(
            User(
                id=SENTINEL_ID,
                username=username or fake.unique.user_name(),
                password=password or fake.password(),
                email=email,
                email_verified=False,
                display_name="",
                active=True,
                superuser=False,
            )
        )
    return factory


@pytest.fixture
async def user_a(user_factory: UserFactory) -> User:
    return await user_factory()


@pytest.fixture
async def user_b(user_factory: UserFactory) -> User:
    return await user_factory()


@pytest.fixture
async def user(user_a: User) -> User:
    return user_a
