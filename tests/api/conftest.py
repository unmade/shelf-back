from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Self
from unittest import mock

import pytest
from httpx import AsyncClient

from app.api import deps
from app.api.main import create_app
from app.app.audit.domain import CurrentUserContext
from app.app.auth.usecases import AuthUseCase
from app.app.files.domain import Namespace
from app.app.files.usecases import NamespaceUseCase, SharingUseCase
from app.app.infrastructure.worker import IWorker
from app.app.photos.usecases.photos import PhotosUseCase
from app.app.users.domain import Account, User
from app.app.users.usecases import UserUseCase
from app.infrastructure.context import UseCases

if TYPE_CHECKING:
    from fastapi import FastAPI


class TestClient(AsyncClient):
    def __init__(self, *, app: FastAPI, **kwargs):
        self.app = app
        super().__init__(app=app, **kwargs)

    def mock_current_user_ctx(self, current_user_ctx: CurrentUserContext) -> Self:
        async def get_current_user_ctx():
            return current_user_ctx

        self.app.dependency_overrides[deps.current_user_ctx] = get_current_user_ctx
        return self

    def mock_namespace(self, namespace: Namespace) -> Self:
        async def get_namespace():
            return namespace

        self.app.dependency_overrides[deps.namespace] = get_namespace
        return self

    def mock_user(self, user: User) -> Self:
        async def get_current_user():
            return CurrentUserContext.User(id=user.id, username=user.username)

        self.app.dependency_overrides[deps.current_user] = get_current_user
        return self


@pytest.fixture(scope="session")
async def app():
    """Application fixture."""
    return create_app(lifespan=mock.MagicMock())


@pytest.fixture
async def client(app):
    """Test client fixture to make requests against app endpoints."""
    async with TestClient(app=app, base_url="http://test") as cli:
        yield cli


@pytest.fixture
def _usecases():
    return mock.MagicMock(
        UseCases,
        auth=mock.MagicMock(AuthUseCase),
        namespace=mock.MagicMock(NamespaceUseCase),
        photos=mock.MagicMock(PhotosUseCase),
        sharing=mock.MagicMock(SharingUseCase),
        user=mock.MagicMock(UserUseCase),
    )


@pytest.fixture
def auth_use_case(_usecases: UseCases):
    """A mocked instance of a AuthUseCase."""
    return _usecases.auth


@pytest.fixture
def ns_use_case(_usecases: UseCases):
    """A mocked instance of a NamespaceUseCase."""
    return _usecases.namespace


@pytest.fixture
def photos_use_case(_usecases: UseCases):
    """A mocked instance of PhotosUseCase."""
    return _usecases.photos


@pytest.fixture
def sharing_use_case(_usecases: UseCases):
    """A mocked instance of a SharingManager."""
    return _usecases.sharing


@pytest.fixture
def user_use_case(_usecases: UseCases):
    """A mock of a UserUseCase instance."""
    return _usecases.user


@pytest.fixture(autouse=True)
async def mock_usecases_deps(app: FastAPI, _usecases: UseCases):
    async def get_usecases():
        return _usecases
    app.dependency_overrides[deps.usecases] = get_usecases


@pytest.fixture
def worker_mock():
    return mock.MagicMock(IWorker)


@pytest.fixture(autouse=True)
async def mock_worker_deps(app: FastAPI, worker_mock: mock.MagicMock):
    async def get_worker():
        return worker_mock
    app.dependency_overrides[deps.worker] = get_worker


@pytest.fixture
async def user():
    return User(id=uuid.uuid4(), username="admin", password="psswd")


@pytest.fixture
async def account(user: User):
    return Account(
        id=uuid.uuid4(),
        email=None,
        username=user.username,
        first_name="John",
        last_name="Doe",
    )


@pytest.fixture
async def namespace(user: User):
    return Namespace(id=uuid.uuid4(), path="admin", owner_id=user.id)
