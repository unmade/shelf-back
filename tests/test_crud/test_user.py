from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app import crud, errors

if TYPE_CHECKING:
    from uuid import UUID

    from app.entities import Namespace, User
    from app.typedefs import DBAnyConn, DBTransaction, StrOrUUID
    from tests.factories import BookmarkFactory, FileFactory

pytestmark = [pytest.mark.asyncio, pytest.mark.database]


async def _get_bookmarks_id(conn: DBAnyConn, user_id: StrOrUUID) -> list[UUID]:
    query = """
        SELECT User { bookmarks: { id } }
        FILTER .id = <uuid>$user_id
    """
    user = await conn.query_required_single(query, user_id=user_id)
    return [entry.id for entry in user.bookmarks]


async def test_add_bookmark(
    tx: DBTransaction,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path)
    await crud.user.add_bookmark(tx, namespace.owner.id, file.id)
    bookmarks = await _get_bookmarks_id(tx, user_id=namespace.owner.id)
    assert len(bookmarks) == 1


async def test_add_bookmark_twice(
    tx: DBTransaction,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path)
    await crud.user.add_bookmark(tx, namespace.owner.id, file.id)
    await crud.user.add_bookmark(tx, namespace.owner.id, file.id)
    bookmarks = await _get_bookmarks_id(tx, user_id=namespace.owner.id)
    assert len(bookmarks) == 1


async def test_add_bookmark_but_user_does_not_exist(
    tx: DBTransaction,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path)
    user_id = uuid.uuid4()

    with pytest.raises(errors.UserNotFound):
        await crud.user.add_bookmark(tx, user_id, file.id)


async def test_add_bookmark_but_file_does_not_exist(tx: DBTransaction, user: User):
    file_id = uuid.uuid4()
    await crud.user.add_bookmark(tx, user.id, file_id)
    bookmarks = await _get_bookmarks_id(tx, user_id=user.id)
    assert len(bookmarks) == 0


async def test_create_user(tx: DBTransaction):
    user = await crud.user.create(tx, "user", "psswd")
    assert user.username == "user"

    user_in_db = await tx.query_required_single("""
        SELECT User {
            username,
            password,
        } FILTER .id = <uuid>$user_id
    """, user_id=user.id)

    assert user.username == "user"
    assert user_in_db.password != "psswd"


async def test_create_user_but_it_already_exists(tx: DBTransaction):
    await crud.user.create(tx, "user", "psswd")

    with pytest.raises(errors.UserAlreadyExists) as excinfo:
        await crud.user.create(tx, "user", "psswd")

    assert str(excinfo.value) == "Username 'user' is taken"


async def test_exists(tx: DBTransaction):
    await crud.user.create(tx, "user", "psswd")
    user = await tx.query_required_single("SELECT User FILTER .username = 'user'")
    assert await crud.user.exists(tx, user_id=user.id)


async def test_exists_but_it_is_not(tx: DBTransaction):
    assert not await crud.user.exists(tx, user_id=uuid.uuid4())


async def test_get_by_id(tx: DBTransaction):
    await crud.user.create(tx, "user", "psswd")
    query = "SELECT User FILTER .username = 'user'"
    user_id = (await tx.query_required_single(query)).id
    user = await crud.user.get_by_id(tx, user_id=user_id)

    assert user.username == "user"
    assert user.superuser is False


async def test_get_by_id_but_it_not_found(tx: DBTransaction):
    user_id = uuid.uuid4()
    with pytest.raises(errors.UserNotFound) as excinfo:
        await crud.user.get_by_id(tx, user_id=user_id)

    assert str(excinfo.value) == f"No user with id: '{user_id}'"


async def test_get_password(tx: DBTransaction):
    await crud.user.create(tx, "user", "psswd")
    user_id, password = await crud.user.get_password(tx, username="user")

    assert user_id
    assert password


async def test_get_password_but_user_not_found(tx: DBTransaction):
    with pytest.raises(errors.UserNotFound) as excinfo:
        await crud.user.get_password(tx, username="user")

    assert str(excinfo.value) == "No user with username: 'user'"


async def test_list_bookmarks(
    tx: DBTransaction,
    namespace: Namespace,
    file_factory: FileFactory,
    bookmark_factory: BookmarkFactory,
):
    user_id = namespace.owner.id
    file_a = await file_factory(namespace.path)
    file_b = await file_factory(namespace.path)
    await file_factory(namespace.path)
    await bookmark_factory(user_id, file_a.id)
    await bookmark_factory(user_id, file_b.id)

    bookmarks = await crud.user.list_bookmarks(tx, user_id)
    assert sorted(bookmarks) == sorted([uuid.UUID(file_a.id), uuid.UUID(file_b.id)])


async def test_list_empty_bookmarks(
    tx: DBTransaction,
    namespace: Namespace,
):
    user_id = namespace.owner.id
    bookmarks = await crud.user.list_bookmarks(tx, user_id)
    assert bookmarks == []


async def test_list_bookmarks_but_user_does_not_exist(tx: DBTransaction):
    user_id = uuid.uuid4()
    with pytest.raises(errors.UserNotFound):
        await crud.user.list_bookmarks(tx, user_id)


async def test_remove_bookmark(
    tx: DBTransaction,
    namespace: Namespace,
    file_factory: FileFactory,
    bookmark_factory: BookmarkFactory,
):
    file = await file_factory(namespace.path)
    await bookmark_factory(namespace.owner.id, file.id)
    bookmarks = await _get_bookmarks_id(tx, user_id=namespace.owner.id)
    assert len(bookmarks) == 1
    await crud.user.remove_bookmark(tx, namespace.owner.id, file.id)
    bookmarks = await _get_bookmarks_id(tx, user_id=namespace.owner.id)
    assert len(bookmarks) == 0


async def test_remove_bookmark_twice(
    tx: DBTransaction,
    namespace: Namespace,
    file_factory: FileFactory,
    bookmark_factory: BookmarkFactory,
):
    file = await file_factory(namespace.path)
    await bookmark_factory(namespace.owner.id, file.id)
    await crud.user.remove_bookmark(tx, namespace.owner.id, file.id)
    await crud.user.remove_bookmark(tx, namespace.owner.id, file.id)
    bookmarks = await _get_bookmarks_id(tx, user_id=namespace.owner.id)
    assert len(bookmarks) == 0


async def test_remove_bookmark_but_user_does_not_exist(
    tx: DBTransaction,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path)
    user_id = uuid.uuid4()

    with pytest.raises(errors.UserNotFound):
        await crud.user.remove_bookmark(tx, user_id, file.id)
