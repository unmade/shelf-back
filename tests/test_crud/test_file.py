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


async def test_empty_trash(db_conn: Connection, user: User):
    path = Path("Trash/a/b/c/d")
    await crud.file.create_folder(db_conn, user.namespace.path, path)
    await db_conn.query("""
        UPDATE File
        FILTER .path = 'Trash' AND .namespace.path = <str>$namespace
        SET { size := 32 }
    """, namespace=str(user.namespace.path))
    await crud.file.empty_trash(db_conn, user.namespace.path)

    trash = await db_conn.query_one("""
        SELECT File {
            size,
            file_count := (
                SELECT count((
                    SELECT File
                    FILTER .path LIKE 'Trash/%' AND .namespace.path = <str>$namespace
                ))
            ),
        }
        FILTER .path = 'Trash' AND .namespace.path = <str>$namespace
    """, namespace=str(user.namespace.path))

    assert trash.size == 0
    assert trash.file_count == 0


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


async def test_exists_but_it_is_not(db_conn: Connection, user: User):
    assert not await crud.file.exists(db_conn, user.namespace.path, "file")


async def test_delete_file(db_conn: Connection, user: User):
    path = Path("folder/file")
    namespace = user.namespace.path
    await crud.file.create(db_conn, namespace, path.parent, size=32, folder=True)
    await crud.file.create(db_conn, namespace, path, size=8)
    await crud.file.delete(db_conn, namespace, path)
    assert not await crud.file.exists(db_conn, namespace, path)

    parent = await crud.file.get(db_conn, namespace, path.parent)
    assert parent.size == 24


async def test_delete_non_empty_folder(db_conn: Connection, user: User):
    namespace = user.namespace.path
    await crud.file.create(db_conn, namespace, "a", size=32, folder=True)
    await crud.file.create(db_conn, namespace, "a/b", size=24, folder=True)
    await crud.file.create(db_conn, namespace, "a/b/c", size=16)

    await crud.file.delete(db_conn, namespace, "a/b")
    assert not await crud.file.exists(db_conn, namespace, "a/b")
    assert not await crud.file.exists(db_conn, namespace, "a/b/c")

    parent = await crud.file.get(db_conn, namespace, "a")
    assert parent.size == 8


async def test_get(db_conn: Connection, user: User):
    await crud.file.create(db_conn, user.namespace.path, "file")
    file = await crud.file.get(db_conn, user.namespace.path, "file")
    assert file.name == "file"
    assert file.path == "file"


async def test_get_but_file_does_not_exists(db_conn: Connection, user: User):
    with pytest.raises(errors.FileNotFound):
        await crud.file.get(db_conn, user.namespace.path, "file")


async def test_list_folder(db_conn: Connection, user: User):
    await crud.file.create_folder(db_conn, user.namespace.path, "a/c")
    await crud.file.create(db_conn, user.namespace.path, "a/b")
    files = await crud.file.list_folder(db_conn, user.namespace.path, "a")
    assert len(files) == 2
    assert files[0].path == "a/c"  # folders listed first
    assert files[1].path == "a/b"


async def test_list_home_folder_without_trash_folder(db_conn: Connection, user: User):
    files = await crud.file.list_folder(db_conn, user.namespace.path, ".")
    assert files == []


async def test_list_home_folder_with_trash_folder(db_conn: Connection, user: User):
    namespace = user.namespace.path
    files = await crud.file.list_folder(db_conn, namespace, ".", with_trash=True)
    assert files[0].path == "Trash"


async def test_list_folder_but_it_is_empty(db_conn: Connection, user: User):
    await crud.file.create_folder(db_conn, user.namespace.path, "a")
    files = await crud.file.list_folder(db_conn, user.namespace.path, "a")
    assert files == []


async def test_list_folder_but_it_not_found(db_conn: Connection, user: User):
    with pytest.raises(errors.FileNotFound):
        await crud.file.list_folder(db_conn, user.namespace.path, "a")


async def test_list_folder_but_it_a_file(db_conn: Connection, user: User):
    await crud.file.create(db_conn, user.namespace.path, "f")
    with pytest.raises(errors.NotADirectory):
        await crud.file.list_folder(db_conn, user.namespace.path, "f")

# todo: test case-insensitive list_folder


async def test_move(db_conn: Connection, user: User):
    namespace = user.namespace.path
    await crud.file.create(db_conn, namespace, "a", size=32, folder=True)
    await crud.file.create(db_conn, namespace, "a/b", size=24, folder=True)
    await crud.file.create(db_conn, namespace, "a/b/c", size=24, folder=True)
    await crud.file.create(db_conn, namespace, "a/b/c/f", size=24)
    await crud.file.create(db_conn, namespace, "a/g", size=8, folder=True)

    # move folder 'c' from 'a/b' to 'a/g'
    await crud.file.move(db_conn, namespace, "a/b/c", "a/g/c")

    with pytest.raises(errors.FileNotFound):
        await crud.file.get(db_conn, namespace, "a/b/c")

    b = await crud.file.get(db_conn, namespace, "a/b")
    assert b.size == 0

    g = await crud.file.get(db_conn, namespace, "a/g")
    assert g.size == 32

    c = await crud.file.get(db_conn, namespace, "a/g/c")
    assert c.size == 24

    f = await crud.file.get(db_conn, namespace, "a/g/c/f")
    assert f.size == 24


async def test_move_with_renaming(db_conn: Connection, user: User):
    namespace = user.namespace.path
    await crud.file.create(db_conn, namespace, "a", folder=True)
    await crud.file.create(db_conn, namespace, "a/b")

    # rename file 'b' to 'c'
    await crud.file.move(db_conn, namespace, "a/b", "a/c")

    with pytest.raises(errors.FileNotFound):
        await crud.file.get(db_conn, namespace, "a/b")

    c = await crud.file.get(db_conn, namespace, "a/c")
    assert c.name == "c"


async def test_move_but_next_path_is_already_taken(db_conn: Connection, user: User):
    namespace = user.namespace.path

    await crud.file.create_folder(db_conn, namespace, "a/b")
    await crud.file.create_folder(db_conn, namespace, "a/c")

    with pytest.raises(errors.FileAlreadyExists):
        await crud.file.move(db_conn, namespace, "a/b", "a/c")


async def test_move_but_from_path_that_not_exists(db_conn: Connection, user: User):
    namespace = user.namespace.path

    with pytest.raises(errors.FileNotFound):
        await crud.file.move(db_conn, namespace, "f", "a")


async def test_move_but_to_path_with_missing_parent(db_conn: Connection, user: User):
    namespace = user.namespace.path
    await crud.file.create(db_conn, namespace, "f")

    with pytest.raises(errors.MissingParent):
        await crud.file.move(db_conn, namespace, "f", "a/f")


async def test_move_but_to_path_that_not_a_folder(db_conn: Connection, user: User):
    namespace = user.namespace.path
    await crud.file.create(db_conn, namespace, "a")
    await crud.file.create(db_conn, namespace, "f")

    with pytest.raises(errors.NotADirectory):
        await crud.file.move(db_conn, namespace, "a", "f/a")


@pytest.mark.parametrize("path", [".", "Trash"])
async def test_move_special_folder(db_conn: Connection, user: User, path):
    namespace = user.namespace.path
    with pytest.raises(AssertionError) as excinfo:
        await crud.file.move(db_conn, namespace, path, "a/b")

    assert str(excinfo.value) == "Can't move Home or Trash folder."


async def test_move_but_paths_are_recursive(db_conn: Connection, user: User):
    namespace = user.namespace.path
    with pytest.raises(AssertionError) as excinfo:
        await crud.file.move(db_conn, namespace, "a/b", "a/b/b")

    assert str(excinfo.value) == "Can't move to itself."
