from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from faker import Faker

from app.app.files.domain import Namespace, Path
from app.app.infrastructure.database import SENTINEL_ID
from app.app.users.domain import Account, User
from app.infrastructure.database.tortoise import models
from app.toolkit import chash
from app.toolkit.mediatypes import MediaType

if TYPE_CHECKING:
    from typing import Protocol
    from uuid import UUID

    from app.app.files.domain import AnyPath
    from app.app.users.repositories import IAccountRepository, IUserRepository
    from app.infrastructure.database.tortoise import TortoiseDatabase
    from app.infrastructure.database.tortoise.repositories import (
        AccountRepository,
        BookmarkRepository,
        NamespaceRepository,
        UserRepository,
    )

    class UserFactory(Protocol):
        async def __call__(
            self,
            username: str | None = None,
            password: str | None = None,
            email: str | None = None,
        ) -> User:
            ...

    class FileFactory(Protocol):
        async def __call__(self, ns_path: str) -> models.File:
            ...

    class FolderFactory(Protocol):
        async def __call__(
            self, ns_path: str, path: AnyPath | None = None, size: int = 0
        ) -> models.File:
            ...

    class NamespaceFactory(Protocol):
        async def __call__(self, path: str, owner_id: UUID) -> Namespace:
            ...

fake = Faker()


@pytest.fixture
def account_repo(tortoise_database: TortoiseDatabase) -> AccountRepository:
    return tortoise_database.account


@pytest.fixture
def bookmark_repo(tortoise_database: TortoiseDatabase) -> BookmarkRepository:
    return tortoise_database.bookmark


@pytest.fixture
def namespace_repo(tortoise_database: TortoiseDatabase) -> NamespaceRepository:
    return tortoise_database.namespace


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
def namespace_factory():
    async def factory(path: str, owner_id: UUID) -> Namespace:
        obj = await models.Namespace.create(
            path=path,
            owner_id=owner_id,
        )
        return Namespace(id=obj.id, path=obj.path, owner_id=owner_id)
    return factory


@pytest.fixture
def file_factory():
    async def factory(ns_path: str) -> models.File:
        mediatype, _ = await models.MediaType.get_or_create(name="plain/text")
        namespace = await models.Namespace.get(path=ns_path)
        name = fake.unique.file_name(category="text", extension="txt")
        return await models.File.create(
            name=name,
            path=name,
            chash=uuid.uuid4().hex,
            size=10,
            modified_at=datetime.now(UTC),
            mediatype=mediatype,
            namespace=namespace,
        )
    return factory


@pytest.fixture
def folder_factory() -> FolderFactory:
    """A factory to create a saved Folder to the Gel."""
    async def factory(
        ns_path: str, path: AnyPath | None = None, size: int = 0
    ) -> models.File:
        mediatype, _ = await models.MediaType.get_or_create(name=MediaType.FOLDER)
        namespace = await models.Namespace.get(path=ns_path)
        path = Path(path or fake.unique.word())
        return await models.File.create(
            name=path.name,
            path=path,
            chash=chash.EMPTY_CONTENT_HASH,
            size=size,
            modified_at=datetime.now(UTC),
            mediatype=mediatype,
            namespace=namespace,
        )
    return factory


@pytest.fixture
async def account(user: User, account_repo: IAccountRepository) -> Account:
    return await account_repo.save(Account(id=SENTINEL_ID, user_id=user.id))


@pytest.fixture
async def namespace_a(user_a: User, namespace_factory: NamespaceFactory) -> Namespace:
    return await namespace_factory(user_a.username.lower(), owner_id=user_a.id)


@pytest.fixture
async def namespace_b(user_b: User, namespace_factory: NamespaceFactory) -> Namespace:
    return await namespace_factory(user_b.username.lower(), owner_id=user_b.id)


@pytest.fixture
async def namespace(namespace_a: Namespace) -> Namespace:
    return namespace_a


@pytest.fixture
async def user_a(user_factory: UserFactory) -> User:
    return await user_factory()


@pytest.fixture
async def user_b(user_factory: UserFactory) -> User:
    return await user_factory()


@pytest.fixture
async def user(user_a: User) -> User:
    return user_a
