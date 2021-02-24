from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from app import crud, errors, mediatypes
from app.entities import File

if TYPE_CHECKING:
    from edgedb import AsyncIOConnection as Connection
    from app.entities import User

pytestmark = [pytest.mark.asyncio]


async def test_create_batch(db_conn: Connection, user: User):
    a_size, f_size = 32, 16
    files = [
        File.construct(  # type: ignore
            name="a",
            path="a",
            size=a_size,
            mtime=time.time(),
            mediatype=mediatypes.folder,
        ),
        File.construct(  # type: ignore
            name="f",
            path="f",
            size=f_size,
            mtime=time.time(),
            mediatype=mediatypes.octet_stream,
        )
    ]
    await crud.file.create_batch(db_conn, user.namespace.path, ".", files=files)

    home = await crud.file.get(db_conn, user.namespace.path, ".")
    assert home.size == a_size + f_size

    files = await crud.file.list_folder(db_conn, user.namespace.path, ".")
    assert len(files) == 2

    assert files[0].name == "a"
    assert files[0].size == a_size
    assert files[0].is_folder() is True
    assert files[0].mediatype == mediatypes.folder

    assert files[1].name == "f"
    assert files[1].size == f_size
    assert files[1].is_folder() is False
    assert files[1].mediatype == mediatypes.octet_stream


async def test_create_batch_but_file_already_exists(db_conn: Connection, user: User):
    file = await crud.file.create(db_conn, user.namespace.path, "f")

    with pytest.raises(errors.FileAlreadyExists):
        await crud.file.create_batch(db_conn, user.namespace.path, ".", files=[file])


async def test_create_batch_but_no_files_given():
    # pass dummy connection, to check that method exists earlier with empty files
    conn = object()
    result = await crud.file.create_batch(conn, "namespace", ".", files=[])
    assert result is None


async def test_create_batch_but_parent_not_exists(db_conn: Connection, user: User):
    file = File.construct()  # type: ignore

    with pytest.raises(errors.FileNotFound):
        await crud.file.create_batch(db_conn, user.namespace.path, "a", files=[file])


async def test_create_batch_but_parent_not_a_folder(db_conn: Connection, user: User):
    file = File.construct()  # type: ignore
    await crud.file.create(db_conn, user.namespace.path, "f")

    with pytest.raises(errors.NotADirectory):
        await crud.file.create_batch(db_conn, user.namespace.path, "f", files=[file])


async def test_create(db_conn: Connection, user: User):
    path = Path("a/b/f")
    await crud.file.create_folder(db_conn, user.namespace.path, path.parent)

    folder = await crud.file.get(db_conn, user.namespace.path, path.parent)
    assert folder.size == 0

    await crud.file.create(db_conn, user.namespace.path, path, size=32)

    file = await db_conn.query_one("""
        SELECT File {
            name, path, size, mediatype: { name }, parent: {
                path, size, mediatype: { name }, parent: {
                    path, size
                }
            }
        }
        FILTER .path = <str>$path AND .namespace.path = <str>$namespace
    """, namespace=str(user.namespace.path), path=str(path))

    assert file.name == path.name
    assert file.path == str(path)
    assert file.size == 32
    assert file.mediatype.name == mediatypes.octet_stream
    assert file.parent.path == str(path.parent)
    assert file.parent.mediatype.name == mediatypes.folder
    assert file.parent.parent.path == str(path.parent.parent)
    assert file.parent.parent.size == 32


async def test_create_updates_parents_size(db_conn: Connection, user: User):
    path = Path("New Folder/file")
    namespace = user.namespace.path
    await crud.file.create(db_conn, namespace, path.parent, mediatype=mediatypes.folder)
    await crud.file.create(db_conn, namespace, path, size=32)

    parents = await crud.file.get_many(db_conn, namespace, path.parents)
    for parent in parents:
        assert parent.size == 32


async def test_create_concurrently(db_conn_factory, user: User):
    paths = [
        Path("a/b/c/e"),
        Path("a/b/c/d"),
        Path("a/b/c/f"),
        Path("a/b/c/g"),
    ]

    MAX_REQUEST = len(paths)
    connections: list[Connection] = await db_conn_factory(MAX_REQUEST)
    conn = connections[0]
    await crud.file.create_folder(conn, user.namespace.path, "a/b/c")

    await asyncio.gather(*(
        crud.file.create(conn, user.namespace.path, path, size=32)
        for conn, path in zip(connections, paths)
    ))

    files = await crud.file.get_many(conn, user.namespace.path, paths)
    assert len(files) == 4

    home = await crud.file.get(conn, user.namespace.path, ".")
    assert home.size == 32 * MAX_REQUEST


async def test_create_but_parent_is_missing(db_conn: Connection, user: User):
    with pytest.raises(errors.MissingParent):
        await crud.file.create(db_conn, user.namespace.path, "New Folder/file")


async def test_create_but_parent_is_not_a_folder(db_conn: Connection, user: User):
    await crud.file.create(db_conn, user.namespace.path, "f")

    with pytest.raises(errors.NotADirectory):
        await crud.file.create(db_conn, user.namespace.path, "f/a")


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


async def test_create_folder_concurrently_with_overlapping_parents(
    db_conn_factory, user: User,
):
    paths = [
        Path("a/b"),
        Path("a/b/c/d"),
        Path("a/b/c/d/e/f/g"),
        Path("a/b/c/d/c"),
    ]

    MAX_REQUEST = len(paths)
    connections = await db_conn_factory(MAX_REQUEST)
    conn = connections[0]

    await asyncio.gather(*(
        crud.file.create_folder(conn, user.namespace.path, path)
        for conn, path in zip(connections, paths)
    ))

    files = list(await conn.query("""
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
    await crud.file.create_folder(db_conn, user.namespace.path, "Trash/a/b")
    await crud.file.create_folder(db_conn, user.namespace.path, "Trash/a/c")
    await crud.file.create(db_conn, user.namespace.path, "Trash/f", size=32)
    await crud.file.create(db_conn, user.namespace.path, "f", size=16)

    trash = await crud.file.empty_trash(db_conn, user.namespace.path)

    assert await crud.file.get(db_conn, user.namespace.path, "Trash") == trash
    files = await crud.file.list_folder(db_conn, user.namespace.path, "Trash")
    assert trash.size == 0
    assert files == []

    home = await crud.file.get(db_conn, user.namespace.path, ".")
    assert home.size == 16


async def test_empty_trash_but_its_already_empty(db_conn: Connection, user: User):
    trash = await crud.file.empty_trash(db_conn, user.namespace.path)
    files = await crud.file.list_folder(db_conn, user.namespace.path, "Trash")
    assert trash.size == 0
    assert files == []


@pytest.mark.parametrize(["mediatype", "is_dir", "exists"], [
    (mediatypes.folder, None, True),
    (mediatypes.octet_stream, None, True),
    (mediatypes.folder, True, True),
    (mediatypes.folder, False, False),
    (mediatypes.octet_stream, True, False),
    (mediatypes.octet_stream, False, True),
])
async def test_exists(db_conn: Connection, user: User, mediatype, is_dir, exists):
    namespace = user.namespace.path
    await crud.file.create(db_conn, namespace, "file", mediatype=mediatype)
    assert await crud.file.exists(db_conn, namespace, "file", is_dir=is_dir) is exists


async def test_exists_but_it_is_not(db_conn: Connection, user: User):
    assert not await crud.file.exists(db_conn, user.namespace.path, "file")


async def test_delete_file(db_conn: Connection, user: User):
    path = Path("folder/file")
    namespace = user.namespace.path
    await crud.file.create(db_conn, namespace, path.parent, mediatype=mediatypes.folder)
    await crud.file.create(db_conn, namespace, path, size=8)

    # ensure parent size has increased
    parent = await crud.file.get(db_conn, namespace, path.parent)
    assert parent.size == 8

    file = await crud.file.delete(db_conn, namespace, path)
    assert file.path == str(path)
    assert not await crud.file.exists(db_conn, namespace, path)

    # ensure parent size has decreased
    parent = await crud.file.get(db_conn, namespace, path.parent)
    assert parent.size == 0


async def test_delete_file_but_it_not_exists(db_conn: Connection, user: User):
    with pytest.raises(errors.FileNotFound):
        await crud.file.delete(db_conn, user.namespace.path, "f")


async def test_delete_non_empty_folder(db_conn: Connection, user: User):
    namespace = user.namespace.path
    await crud.file.create(db_conn, namespace, "a", mediatype=mediatypes.folder)
    await crud.file.create(db_conn, namespace, "a/b", mediatype=mediatypes.folder)
    await crud.file.create(db_conn, namespace, "a/b/c", size=8)

    # ensure parent size has increased
    a, b = await crud.file.get_many(db_conn, namespace, ["a", "a/b"])
    assert a.size == 8
    assert b.size == 8

    await crud.file.delete(db_conn, namespace, "a/b")
    assert not await crud.file.exists(db_conn, namespace, "a/b")
    assert not await crud.file.exists(db_conn, namespace, "a/b/c")

    # ensure size has decreased
    parent = await crud.file.get(db_conn, namespace, "a")
    assert parent.size == 0


async def test_get(db_conn: Connection, user: User):
    await crud.file.create(db_conn, user.namespace.path, "file")
    file = await crud.file.get(db_conn, user.namespace.path, "file")
    assert file.name == "file"
    assert file.path == "file"


async def test_get_but_file_does_not_exists(db_conn: Connection, user: User):
    with pytest.raises(errors.FileNotFound):
        await crud.file.get(db_conn, user.namespace.path, "file")


async def test_get_many(db_conn: Connection, user: User):
    namespace = user.namespace.path
    await crud.file.create(db_conn, namespace, "a", mediatype=mediatypes.folder)
    await crud.file.create(db_conn, namespace, "a/b", mediatype=mediatypes.folder)
    await crud.file.create(db_conn, namespace, "a/c", mediatype=mediatypes.folder)
    await crud.file.create(db_conn, namespace, "a/f")

    paths = ["a", "a/c", "a/f", "a/d"]
    files = await crud.file.get_many(db_conn, namespace, paths=paths)

    assert len(files) == 3
    for file, path in zip(files, paths[:-1]):
        assert file.path == path


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
    conn = db_conn  # alias to save some line space
    namespace = str(user.namespace.path)
    await crud.file.create_folder(conn, namespace, "a/b/c")
    await crud.file.create(conn, namespace, "a/b/c/f", size=24)
    await crud.file.create(conn, namespace, "a/g", size=8, mediatype=mediatypes.folder)

    # move folder 'c' from 'a/b' to 'a/g'
    await crud.file.move(conn, namespace, "a/b/c", "a/g/c")

    assert not await crud.file.exists(conn, namespace, "a/b/c")

    query = """
        SELECT File { size, parent: { id } }
        FILTER
            .path IN array_unpack(<array<str>>$paths)
            AND
            .namespace.path = <str>$namespace
        ORDER BY .path ASC
    """

    paths = ["a", "a/b", "a/g", "a/g/c", "a/g/c/f"]
    a, b, g, c, f = await db_conn.query(query, namespace=namespace, paths=paths)

    assert b.size == 0
    assert b.parent.id == a.id

    assert g.size == 32
    assert g.parent.id == a.id

    assert c.size == 24
    assert c.parent.id == g.id

    assert f.size == 24
    assert f.parent.id == c.id


async def test_move_with_renaming(db_conn: Connection, user: User):
    namespace = user.namespace.path
    await crud.file.create(db_conn, namespace, "a", mediatype=mediatypes.folder)
    await crud.file.create(db_conn, namespace, "a/f")

    # rename file 'f' to 'f.txt'
    await crud.file.move(db_conn, namespace, "a/f", "a/f.txt")

    assert not await crud.file.exists(db_conn, namespace, "a/f")

    f = await crud.file.get(db_conn, namespace, "a/f.txt")
    assert f.name == "f.txt"


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


@pytest.mark.parametrize(["name", "next_name"], [
    ("f.txt", "f (1).txt"),
    ("f.tar.gz", "f (1).tar.gz"),
    ("f (1).tar.gz", "f (1) (1).tar.gz"),
])
async def test_next_path(db_conn: Connection, user: User, name, next_name):
    await crud.file.create_folder(db_conn, user.namespace.path, "a/b")
    await crud.file.create(db_conn, user.namespace.path, f"a/b/{name}")

    next_path = await crud.file.next_path(db_conn, user.namespace.path, f"a/b/{name}")
    assert next_path == f"a/b/{next_name}"
    assert not (await crud.file.exists(db_conn, user.namespace.path, next_name))


async def test_next_path_is_sequential(db_conn: Connection, user: User):
    await crud.file.create(db_conn, user.namespace.path, "f.tar.gz")
    await crud.file.create(db_conn, user.namespace.path, "f (1).tar.gz")

    next_path = await crud.file.next_path(db_conn, user.namespace.path, "f.tar.gz")
    assert next_path == "f (2).tar.gz"
    assert not (await crud.file.exists(db_conn, user.namespace.path, "f (2).tar.gz"))


async def test_inc_size_batch(db_conn: Connection, user: User):
    namespace = user.namespace.path
    await crud.file.create_folder(db_conn, namespace, "a/b")
    await crud.file.create_folder(db_conn, namespace, "a/c")
    await crud.file.inc_size_batch(db_conn, namespace, paths=["a", "a/c"], size=16)

    a, b, c = await crud.file.get_many(db_conn, namespace, paths=["a", "a/b", "a/c"])
    assert a.size == 16
    assert b.size == 0
    assert c.size == 16


async def test_inc_size_batch_but_size_is_zero():
    # pass dummy connection, to check that method exists earlier with empty files
    conn = object()
    result = await crud.file.inc_size_batch(conn, "namespace", paths=["a/b"], size=0)
    assert result is None
