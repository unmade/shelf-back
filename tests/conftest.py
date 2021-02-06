from __future__ import annotations

from io import BytesIO
from unittest import mock

import pytest
from faker import Faker
from starlette.testclient import TestClient as StarletteTestClient

from app import actions, config, crud, db, security
from app.main import create_app

fake = Faker()


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


@pytest.fixture(autouse=True)
def replace_storage_root_dir_with_tmp_path(tmp_path):
    """Monkey patches storage root_dir with a temporary directory"""
    from app.storage import storage

    storage.root_dir = tmp_path


@pytest.fixture
def user_factory():
    """Creates a new user, namespace, home and trash directories"""
    def _user_factory(
        username: str = None, password: str = "root", hash_password: bool = False,
    ):
        username = username or fake.simple_profile()["username"]
        with db.SessionManager() as db_session:
            # Hashing password is an expensive operation, so do it only when need it.
            if hash_password:
                account = actions.create_account(db_session, username, password)
            else:
                with mock.patch("app.security.make_password", return_value=password):
                    account = actions.create_account(db_session, username, password)

            db_session.commit()
            return account
    return _user_factory


@pytest.fixture
def file_factory():
    """Creates dummy file, put it in a storage and save to database."""
    def _file_factory(user_id: int, path: str = None):
        path = path or fake.file_name(category="text", extension="txt")
        with db.SessionManager() as db_session:
            file = BytesIO(b"I'm Dummy File!")
            account = crud.user.get_account(db_session, user_id)
            namespace = account.namespace
            result = actions.save_file(db_session, namespace, path, file)
            db_session.commit()
            return result
    return _file_factory
