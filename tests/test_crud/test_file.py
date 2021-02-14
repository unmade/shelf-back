from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from app import crud, errors

if TYPE_CHECKING:
    from edgedb import AsyncIOConnection as Connection, AsyncIOPool as Pool
    from app.entities import User

pytestmark = [pytest.mark.asyncio]


async def test_create(db_conn: Connection, user: User):
    await crud.file.create(db_conn, user.namespace.path, "New Folder", folder=True)
    await crud.file.create(db_conn, user.namespace.path, "New Folder/file", size=32)

    file = await db_conn.query_one("""
        SELECT File {
            name, path, size, is_dir, parent: {
                path, size, is_dir, parent: {
                    path
                }
            }
        }
        FILTER .path = <str>$path AND .namespace.path = <str>$namespace
    """, namespace=str(user.namespace.path), path="New Folder/file")

    assert file.name == "file"
    assert file.path == "New Folder/file"
    assert file.size == 32
    assert file.is_dir is False
    assert file.parent.path == "New Folder"
    assert file.parent.is_dir is True
    assert file.parent.parent.path == "."


async def test_create_but_parent_is_missing(db_conn: Connection, user: User):
    with pytest.raises(errors.MissingParent):
        await crud.file.create(db_conn, user.namespace.path, "New Folder/file")


async def test_create_but_file_already_exists(db_conn: Connection, user: User):
    with pytest.raises(errors.FileAlreadyExists):
        await crud.file.create(db_conn, user.namespace.path, ".")


async def test_create_folder(db_conn: Connection, user: User):
    path = Path("a/b/c")
    await crud.file.create_folder(db_conn, user.namespace.path, path)

    query = """
        SELECT File { id, path, parent: { id } }
        FILTER
            .path IN array_unpack(<array<str>>$paths)
            AND
            .namespace.path = <str>$namespace
    """

    paths = [str(path)] + [str(p) for p in path.parents]
    result = await db_conn.query(query, namespace=str(user.namespace.path), paths=paths)

    home, a, b, c = result
    assert home.path == "."
    assert not home.parent

    assert a.path == "a"
    assert a.parent.id == home.id

    assert b.path == "a/b"
    assert b.parent.id == a.id

    assert c.path == "a/b/c"
    assert c.parent.id == b.id


async def test_create_folder_but_with_overlapping_parents(
    db_pool: Pool, db_conn: Connection, user: User,
):
    paths = [
        Path("a/b"),
        Path("a/b/c/d"),
        Path("a/b/c/d/e/f/g"),
        Path("a/b/c/d/c"),
    ]

    MAX_REQUEST = len(paths)

    # ensure we do not acquire more requests that we actually have in the pool
    assert MAX_REQUEST < db_pool.min_size

    connections = await asyncio.gather(*(
        db_pool.acquire() for _ in range(MAX_REQUEST)
    ))

    try:
        await asyncio.gather(*(
            crud.file.create_folder(conn, user.namespace.path, path)
            for conn, path in zip(connections, paths)
        ))
    finally:
        await asyncio.gather(*(
            db_pool.release(conn) for conn in connections
        ))

    files = list(await db_conn.query("""
        SELECT File { id, path, parent: { id } }
        FILTER
            .path != 'Trash'
            AND
            .namespace.path = <str>$namespace
        ORDER BY str_lower(.path) ASC
    """, namespace=str(user.namespace.path)))

    expected_path = [
        ".",
        "a",
        "a/b",
        "a/b/c",
        "a/b/c/d",
        "a/b/c/d/c",
        "a/b/c/d/e",
        "a/b/c/d/e/f",
        "a/b/c/d/e/f/g",
    ]
    assert [file.path for file in files] == expected_path

    parent = files[0]
    for file in files[1:6]:
        assert file.parent.id == parent.id
        parent = file

    parent = files[4]
    for file in files[6:]:
        assert file.parent.id == parent.id
        parent = file


async def test_create_folder_but_folder_exists(db_conn: Connection, user: User):
    await crud.file.create_folder(db_conn, user.namespace.path, "folder")

    with pytest.raises(errors.FileAlreadyExists):
        await crud.file.create_folder(db_conn, user.namespace.path, "folder")


async def test_create_folder_but_path_not_a_dir(db_conn: Connection, user: User):
    await crud.file.create(db_conn, user.namespace.path, "data")

    with pytest.raises(errors.NotADirectory):
        await crud.file.create_folder(db_conn, user.namespace.path, "data/file")


@pytest.mark.parametrize(["is_dir", "folder", "exists"], [
    (True, None, True),
    (False, None, True),
    (True, True, True),
    (True, False, False),
    (False, True, False),
    (False, False, True),
])
async def test_exists(db_conn: Connection, user: User, is_dir, folder, exists):
    namespace = user.namespace.path
    await crud.file.create(db_conn, namespace, "file", folder=is_dir)
    assert await crud.file.exists(db_conn, namespace, "file", folder=folder) is exists


async def test_exists_but_it_is_not(db_conn: Connection, user_factory):
    user = await user_factory()
    assert not await crud.file.exists(db_conn, user.namespace.path, "file")


async def test_get(db_conn: Connection, user_factory):
    user = await user_factory()
    await crud.file.create(db_conn, user.namespace.path, "file")
    file = await crud.file.get(db_conn, user.namespace.path, "file")
    assert file.name == "file"
    assert file.path == "file"


async def test_get_but_file_does_not_exists(db_conn: Connection, user: User):
    with pytest.raises(errors.FileNotFound):
        await crud.file.get(db_conn, user.namespace.path, "file")
