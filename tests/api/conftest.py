from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest import mock

import pytest
from httpx import AsyncClient

from app.api import deps
from app.app.files.domain import Namespace
from app.app.users.domain import Account, User
from app.main import create_app

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
    return create_app()


@pytest.fixture
async def client(app):
    """Test client fixture to make requests against app endpoints."""
    async with TestClient(app=app, base_url="http://test") as cli:
        yield cli


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


@pytest.fixture
def auth_use_case(app: FastAPI):
    """A mocked instance of a AuthUseCase."""
    usecases = app.state.provider.usecases
    new = mock.MagicMock(usecases.auth)
    with mock.patch.object(usecases, "auth", new) as patch:
        yield patch


@pytest.fixture
def ns_use_case(app: FastAPI):
    """A mocked instance of a NamespaceUseCase."""
    usecases = app.state.provider.usecases
    new = mock.MagicMock(usecases.namespace)
    with mock.patch.object(usecases, "namespace", new) as patch:
        yield patch


@pytest.fixture
def ns_service(app: FastAPI):
    """A mock of a NamespaceService instance."""
    services = app.state.provider.services
    new = mock.MagicMock(services.namespace)
    with mock.patch.object(services, "namespace", new) as patch:
        yield patch


@pytest.fixture
def user_service(app: FastAPI):
    """A mock of a UserService instance."""
    services = app.state.provider.services
    spec = mock.MagicMock(services.user)
    with mock.patch.object(services, "user", spec) as mocked:
        yield mocked


@pytest.fixture
def user_use_case(app: FastAPI):
    """A mock of a UserUseCase instance."""
    usecases = app.state.provider.usecases
    spec = mock.MagicMock(usecases.user)
    with mock.patch.object(usecases, "user", spec) as mocked:
        yield mocked


@pytest.fixture
def sharing_use_case(app: FastAPI):
    """A mocked instance of a SharingManager."""
    usecases = app.state.provider.usecases
    new = mock.MagicMock(usecases.sharing)
    with mock.patch.object(usecases, "sharing", new) as patch:
        yield patch
