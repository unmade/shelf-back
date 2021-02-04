from __future__ import annotations

import pytest
from pytest_factoryboy import register
from starlette.testclient import TestClient as StarletteTestClient

from app import config, db, security
from app.main import create_app

from . import factories

register(factories.UserFactory)


class TestClient(StarletteTestClient):
    def login(self, user_id: int) -> TestClient:
        """
        Authenticates given user by creating access token and setting it as
        the Authorization header.
        """
        token = security.create_access_token(user_id)
        self.headers.update({"Authorization": f"Bearer {token}"})
        return self


@pytest.fixture
def client():
    """Test client fixture to make requests against app endpoints"""
    return TestClient(create_app())


@pytest.fixture(autouse=True)
def create_schema_for_in_memory_sqlite(request):
    """Fixture automatically creates schema when running with in-memory SQLite"""
    if config.DATABASE_DSN == "sqlite://":  # pragma: no cover
        db.Base.metadata.create_all(bind=db.engine)
