from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from app import crud

if TYPE_CHECKING:
    from edgedb import AsyncIOConnection, AsyncIOPool

pytestmark = [pytest.mark.asyncio]


async def test_create_folder(db_conn: AsyncIOConnection, user_factory):
    user = await user_factory()
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


async def test_create_several_folders_with_overlapping_parents_concurrently(
    db_pool: AsyncIOPool, db_conn: AsyncIOConnection, user_factory,
):
    user = await user_factory()

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

    query = """
        SELECT File { id, path, parent: { id } }
        FILTER
            .path != 'Trash'
            AND
            .namespace.path = <str>$namespace
        ORDER BY str_lower(.path) ASC
    """

    files = list(await db_conn.query(query, namespace=str(user.namespace.path)))

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
