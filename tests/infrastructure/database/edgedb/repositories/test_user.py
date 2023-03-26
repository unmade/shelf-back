from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.app.files.domain import SENTINEL_ID, Namespace
from app.app.users.domain import User

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.files.domain import File
    from app.app.users.repositories import IUserRepository
    from app.infrastructure.database.edgedb.repositories import UserRepository
    from app.infrastructure.database.edgedb.typedefs import EdgeDBAnyConn
    from app.typedefs import StrOrUUID

    from ..conftest import FileFactory

pytestmark = [pytest.mark.asyncio]


async def _save_bookmark(conn: EdgeDBAnyConn, user_id: StrOrUUID, file_id: StrOrUUID):
    query = """
        UPDATE User
        FILTER .id = <uuid>$user_id
        SET { bookmarks += (
            SELECT File FILTER .id = <uuid>$file_id
        ) }"""
    await conn.query_required_single(query, user_id=user_id, file_id=file_id)


async def _list_bookmarks_id(conn: EdgeDBAnyConn, user_id: StrOrUUID) -> list[UUID]:
    query = """SELECT User { bookmarks: { id } } FILTER .id = <uuid>$user_id"""
    user = await conn.query_required_single(query, user_id=user_id)
    return [entry.id for entry in user.bookmarks]


class TestAddBookmark:
    async def test(self, user: User, file: File, user_repo: UserRepository):
        await user_repo.add_bookmark(user.id, file.id)
        bookmarks = await _list_bookmarks_id(user_repo.conn, user.id)
        assert len(bookmarks) == 1

    async def test_adding_twice(
        self, user: User, file: File, user_repo: UserRepository
    ):
        await user_repo.add_bookmark(user.id, file.id)
        await user_repo.add_bookmark(user.id, file.id)
        bookmarks = await _list_bookmarks_id(user_repo.conn, user.id)
        assert len(bookmarks) == 1

    async def test_when_user_does_not_exist(
        self, file: File, user_repo: UserRepository
    ):
        user_id = uuid.uuid4()
        with pytest.raises(User.NotFound):
            await user_repo.add_bookmark(user_id, file.id)

    async def test_when_file_does_not_exist(
        self, user: User, user_repo: UserRepository
    ):
        file_id = uuid.uuid4()
        await user_repo.add_bookmark(user.id, file_id)
        bookmarks = await _list_bookmarks_id(user_repo.conn, user.id)
        assert len(bookmarks) == 0


class TestGetByID:
    async def test(self, user: User, user_repo: UserRepository):
        retrieved_user = await user_repo.get_by_id(user.id)
        assert retrieved_user == user

    async def test_when_user_does_not_exist(self, user_repo: UserRepository):
        user_id = uuid.uuid4()
        with pytest.raises(User.NotFound):
            await user_repo.get_by_id(user_id)


class TestGetByUsername:
    async def test(self, user: User, user_repo: UserRepository):
        retrieved_user = await user_repo.get_by_username(user.username)
        assert retrieved_user == user

    async def test_when_user_does_not_exist(self, user_repo: UserRepository):
        username = "admin"
        with pytest.raises(User.NotFound):
            await user_repo.get_by_username(username)


class TestListBookmarks:
    async def test(
        self, namespace: Namespace, file_factory: FileFactory, user_repo: UserRepository
    ):
        file_a = await file_factory(namespace.path)
        file_b = await file_factory(namespace.path)
        await file_factory(namespace.path)
        await _save_bookmark(user_repo.conn, namespace.owner_id, file_a.id)
        await _save_bookmark(user_repo.conn, namespace.owner_id, file_b.id)
        bookmarks = await user_repo.list_bookmarks(namespace.owner_id)
        assert sorted(str(v) for v in bookmarks) == sorted([file_a.id, file_b.id])

    async def test_when_no_bookmarks(self, user: User, user_repo: UserRepository):
        bookmarks = await user_repo.list_bookmarks(user.id)
        assert bookmarks == []

    async def test_when_user_does_not_exist(self, user_repo: UserRepository):
        user_id = uuid.uuid4()
        with pytest.raises(User.NotFound):
            await user_repo.list_bookmarks(user_id)


class TestRemoveBookmark:
    async def test(
        self, namespace: Namespace, file_factory: FileFactory, user_repo: UserRepository
    ):
        user_id = namespace.owner_id
        file_a = await file_factory(namespace.path)
        file_b = await file_factory(namespace.path)
        await _save_bookmark(user_repo.conn, user_id, file_a.id)
        await _save_bookmark(user_repo.conn, user_id, file_b.id)
        await user_repo.remove_bookmark(user_id, file_a.id)
        bookmarks = await _list_bookmarks_id(user_repo.conn, user_id)
        assert bookmarks == [uuid.UUID(file_b.id)]

    async def test_removing_bookmark_twice(
        self, namespace: Namespace, file_factory: FileFactory, user_repo: UserRepository
    ):
        user_id = namespace.owner_id
        file = await file_factory(namespace.path)
        await _save_bookmark(user_repo.conn, user_id, file.id)
        await user_repo.remove_bookmark(user_id, file.id)
        await user_repo.remove_bookmark(user_id, file.id)
        bookmarks = await _list_bookmarks_id(user_repo.conn, user_id)
        assert bookmarks == []

    async def test_when_user_does_not_exist(self, user_repo: UserRepository):
        user_id, file_id = uuid.uuid4(), uuid.uuid4()
        with pytest.raises(User.NotFound):
            await user_repo.remove_bookmark(user_id, file_id)


class TestSave:
    async def test(self, user_repo: IUserRepository):
        user = User(id=SENTINEL_ID, username="admin", password="psswd")
        created_user = await user_repo.save(user)
        assert created_user.id != SENTINEL_ID
        assert user.username == user.username
        assert user.password == user.password
        assert user.superuser is False

    async def test_when_user_already_exists(self, user_repo: IUserRepository):
        user = User(id=SENTINEL_ID, username="admin", password="psswd")
        await user_repo.save(user)

        with pytest.raises(User.AlreadyExists) as excinfo:
            await user_repo.save(user)

        assert str(excinfo.value) == "Username 'admin' is taken"
