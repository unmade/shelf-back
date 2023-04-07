from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest import mock

import pytest
from httpx import AsyncClient

from app.api import deps
from app.api.main import create_app
from app.app.auth.usecases import AuthUseCase
from app.app.files.domain import Namespace
from app.app.files.usecases import NamespaceUseCase, SharingUseCase
from app.app.users.domain import Account, User
from app.app.users.usecases import UserUseCase
from app.infrastructure.context import UseCases

if TYPE_CHECKING:
    from fastapi import FastAPI


class TestClient(AsyncClient):
    def __init__(self, *, app: FastAPI, **kwargs):
        self.app = app
        super().__init__(app=app, **kwargs)

    def mock_namespace(self, namespace: Namespace):
        async def get_namespace():
            return namespace

        self.app.dependency_overrides[deps.namespace] = get_namespace
        return self

    def mock_user(self, user: User):
        async def get_current_user():
            return user

        self.app.dependency_overrides[deps.current_user] = get_current_user
        return self


@pytest.fixture(scope="session")
def app():
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
def sharing_use_case(_usecases: UseCases):
    """A mocked instance of a SharingManager."""
    return _usecases.sharing


@pytest.fixture
def user_use_case(_usecases: UseCases):
    """A mock of a UserUseCase instance."""
    return _usecases.user


@pytest.fixture(autouse=True)
def mock_usecases_deps(app: FastAPI, _usecases: UseCases):
    def get_usecases():
        return _usecases
    app.dependency_overrides[deps.usecases] = get_usecases


@pytest.fixture
async def user():
    return User(id=uuid.uuid4(), username="admin", password="psswd")


@pytest.fixture
async def account(user: User):
    return Account(
        id=uuid.uuid4(),
        username=user.username,
        first_name="John",
        last_name="Doe",
    )


@pytest.fixture
async def namespace(user: User):
    return Namespace(id=uuid.uuid4(), path="admin", owner_id=user.id)
