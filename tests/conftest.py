from __future__ import annotations

from pathlib import Path

import pytest
from faker import Faker
from starlette.testclient import TestClient as StarletteTestClient

from app import config, crud, db, security
from app.main import create_app
from app.storage import storage

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
    """Creates a new user, namespace, root and trash directories"""
    def _user_factory(username: str = None, password: str = "root"):
        with db.SessionManager() as db_session:
            username = username or fake.simple_profile()["username"]
            # TODO: hashing password is an expensive operation. Maybe it would be better
            # to have a special flag and hash it only when needed.
            user = crud.user.create(db_session, username, password)
            ns = crud.namespace.create(db_session, username, owner_id=user.id)
            root_dir = storage.mkdir(ns.path)
            trash_dir = storage.mkdir(Path(ns.path).joinpath(config.TRASH_FOLDER_NAME))
            root = crud.file.create(db_session, root_dir, ns.id, rel_to=ns.path)
            db_session.flush()
            crud.file.create(
                db_session, trash_dir, ns.id, rel_to=ns.path, parent_id=root.id
            )
            db_session.commit()
            db_session.refresh(user)
            return user
    return _user_factory
