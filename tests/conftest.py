from __future__ import annotations

from io import BytesIO
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
    def _user_factory(
        username: str = None, password: str = "root", hash_password: bool = False,
    ):
        with db.SessionManager() as db_session:
            username = username or fake.simple_profile()["username"]
            # Hashing password is an expensive operation. Maybe it would be better
            # to have a special flag and hash it only when needed.
            if hash_password:
                user = crud.user.create(db_session, username, password)
            else:
                from unittest import mock

                with mock.patch("app.security.make_password", return_value=password):
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


@pytest.fixture
def file_factory():
    """Creates dummy file, put it in a storage and save to database."""
    def _file_factory(user_id: int, path: str = None):
        path = path or fake.file_name(category="text", extension="txt")
        with db.SessionManager() as db_session:
            file = BytesIO(b"I'm Dummy File!")
            account = crud.user.get_account(db_session, user_id)
            namespace = account.namespace

            relpath = Path(path)
            ns_path = Path(namespace.path)
            fullpath = ns_path / relpath

            if not storage.is_dir_exists(fullpath.parent):
                # todo: catch exception if creation fails
                storage.mkdir(fullpath.parent)

            parent = crud.file.get_folder(db_session, namespace.id, str(relpath.parent))
            if not parent:
                parent = crud.file.create_parents(
                    db_session,
                    [storage.get(ns_path / p) for p in relpath.parents],
                    namespace_id=namespace.id,
                    rel_to=namespace.path,
                )

            file_exists = storage.is_exists(fullpath)
            storage_file = storage.save(fullpath, file)

            if file_exists:
                prev_file = storage.get(fullpath)
                result = crud.file.update(
                    db_session,
                    storage_file,
                    namespace_id=namespace.id,
                    rel_to=namespace.path,
                )
                size_inc = storage_file.size - prev_file.size
            else:
                result = crud.file.create(
                    db_session,
                    storage_file,
                    namespace_id=namespace.id,
                    rel_to=namespace.path,
                    parent_id=parent.id,
                )
                size_inc = storage_file.size

            crud.file.inc_folder_size(
                db_session, namespace_id=namespace.id, path=result.path, size=size_inc,
            )

            db_session.commit()
            db_session.refresh(result)

            return result
    return _file_factory
