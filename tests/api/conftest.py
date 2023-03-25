from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest import mock

import pytest
from httpx import AsyncClient

from app.api import deps
from app.domain.entities import Account, Namespace, User
from app.main import create_app
from app.tokens import AccessTokenPayload

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.typedefs import StrOrUUID


class TestClient(AsyncClient):
    def __init__(self, *, app: FastAPI, **kwargs):
        self.app = app
        super().__init__(app=app, **kwargs)

    def login(self, user_id: StrOrUUID) -> TestClient:
        """
        Authenticates given user by creating access token and setting it as
        the Authorization header.
        """
        token = AccessTokenPayload.create(str(user_id)).encode()
        self.headers.update({"Authorization": f"Bearer {token}"})
        return self

    def mock_namespace(self, namespace: Namespace):
        async def get_namespace():
            return namespace

        self.app.dependency_overrides[deps.namespace] = get_namespace
        return self

    def mock_user(self, user: User):
        async def get_current_user_id():
            return user.id

        async def get_current_user():
            return user

        self.app.dependency_overrides[deps.current_user_id] = get_current_user_id
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
def ns_manager(app: FastAPI):
    """A mocked instance of a NamespaceManager."""
    managers = app.state.provider.manager
    new = mock.MagicMock(managers.namespace)
    with mock.patch.object(managers, "namespace", new) as patch:
        yield patch


@pytest.fixture
def ns_service(app: FastAPI):
    """A mock of a NamespaceService instance."""
    service = app.state.provider.service
    new = mock.MagicMock(service.namespace)
    with mock.patch.object(service, "namespace", new) as patch:
        yield patch


@pytest.fixture
def user_service(app: FastAPI):
    """A mock of a UserService instance."""
    service = app.state.provider.service
    spec = mock.MagicMock(service.user)
    with mock.patch.object(service, "user", spec) as mocked:
        yield mocked


@pytest.fixture
def sharing_manager(app: FastAPI):
    """A mocked instance of a SharingManager."""
    managers = app.state.provider.manager
    new = mock.MagicMock(managers.sharing)
    with mock.patch.object(managers, "sharing", new) as patch:
        yield patch
