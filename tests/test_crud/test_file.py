from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from app import crud, errors
from app.entities import File
from app.mediatypes import FOLDER, OCTET_STREAM

if TYPE_CHECKING:
    from app.entities import Namespace
    from app.typedefs import DBPool

pytestmark = [pytest.mark.asyncio]


async def test_create(db_pool: DBPool, namespace: Namespace):
    path = Path("a/b/f")
    for parent in list(reversed(path.parents))[1:]:
        await crud.file.create(db_pool, namespace.path, parent, mediatype=FOLDER)

    folder = await crud.file.get(db_pool, namespace.path, path.parent)
    assert folder.size == 0

    await crud.file.create(db_pool, namespace.path, path, size=32)

    file = await db_pool.query_one("""
        SELECT File {
            name, path, size, mediatype: { name }, parent: {
                path, size, mediatype: { name }, parent: {
                    path, size
                }
            }
        }
        FILTER .path = <str>$path AND .namespace.path = <str>$namespace
    """, namespace=str(namespace.path), path=str(path))

    assert file.name == path.name
    assert file.path == str(path)
    assert file.size == 32
    assert file.mediatype.name == OCTET_STREAM
    assert file.parent.path == str(path.parent)
    assert file.parent.mediatype.name == FOLDER
    assert file.parent.parent.path == str(path.parent.parent)
    assert file.parent.parent.size == 32


async def test_create_updates_parents_size(db_pool: DBPool, namespace: Namespace):
    path = Path("New Folder/file")
    await crud.file.create(db_pool, namespace.path, path.parent, mediatype=FOLDER)
    await crud.file.create(db_pool, namespace.path, path, size=32)

    parents = await crud.file.get_many(db_pool, namespace.path, path.parents)
    for parent in parents:
        assert parent.size == 32


async def test_create_is_case_insensitive(db_pool: DBPool, namespace: Namespace):
    await crud.file.create(db_pool, namespace.path, "A", mediatype=FOLDER)
    await crud.file.create(db_pool, namespace.path, "a/f", size=32)

    file = await crud.file.get(db_pool, namespace.path, "a/f")
    assert file.path == "A/f"  # original case of parent is preserved


async def test_create_but_parent_is_missing(db_pool: DBPool, namespace: Namespace):
    with pytest.raises(errors.MissingParent):
        await crud.file.create(db_pool, namespace.path, "New Folder/file")


async def test_create_but_parent_is_not_a_folder(db_pool: DBPool, namespace: Namespace):
    await crud.file.create(db_pool, namespace.path, "f")

    with pytest.raises(errors.NotADirectory):
        await crud.file.create(db_pool, namespace.path, "f/a")


async def test_create_but_file_already_exists(db_pool: DBPool, namespace: Namespace):
    with pytest.raises(errors.FileAlreadyExists):
        await crud.file.create(db_pool, namespace.path, ".")


async def test_create_batch(db_pool: DBPool, namespace: Namespace):
    a_size, f_size = 32, 16
    files = [
        File.construct(  # type: ignore
            name="a",
            path="a",
            size=a_size,
            mtime=time.time(),
            mediatype=FOLDER,
        ),
        File.construct(  # type: ignore
            name="f",
            path="f",
            size=f_size,
            mtime=time.time(),
            mediatype=OCTET_STREAM,
        )
    ]
    await crud.file.create_batch(db_pool, namespace.path, ".", files=files)

    home = await crud.file.get(db_pool, namespace.path, ".")
    assert home.size == a_size + f_size

    files = await crud.file.list_folder(db_pool, namespace.path, ".")
    assert len(files) == 2

    assert files[0].name == "a"
    assert files[0].size == a_size
    assert files[0].is_folder() is True
    assert files[0].mediatype == FOLDER

    assert files[1].name == "f"
    assert files[1].size == f_size
    assert files[1].is_folder() is False
    assert files[1].mediatype == OCTET_STREAM


async def test_create_batch_but_all_the_same(db_pool: DBPool, namespace: Namespace):
    # Insert Files with media type that does not exists in the database.
    # This test assures that first query inserts a file and inserts a mediatype
    # and second query inserts a file, but selects a mediatype.
    mediatypes = ["application/x-create-batch-1", "application/x-create-batch-2"]
    all_paths = [("a", "b"), ("c", "d")]
    to_create = [
        File.construct(  # type: ignore
            name=path,
            path=path,
            size=0,
            mtime=time.time(),
            mediatype=mediatype,
        )
        for mediatype, paths in zip(mediatypes, all_paths)
        for path in paths
    ]

    await crud.file.create_batch(db_pool, namespace.path, ".", files=to_create)

    files = await crud.file.list_folder(db_pool, namespace.path, ".")
    assert len(files) == 4

    for i, mediatype, paths in zip(range(0, len(files), 2), mediatypes, all_paths):
        for j, path in enumerate(paths):
            assert files[i + j].name == path
            assert files[i + j].mediatype == mediatype


async def test_create_batch_is_case_insensitive(db_pool: DBPool, namespace: Namespace):
    to_create = [
        File.construct(  # type: ignore
            name="B",
            path="A/B",
            size=0,
            mtime=time.time(),
            mediatype=FOLDER,
        ),
        File.construct(  # type: ignore
            name="f",
            path="a/f",
            size=8,
            mtime=time.time(),
            mediatype=OCTET_STREAM,
        )
    ]
    await crud.file.create(db_pool, namespace.path, "A", mediatype=FOLDER)

    await crud.file.create_batch(db_pool, namespace.path, "a", files=to_create)

    files = await crud.file.list_folder(db_pool, namespace.path, "A")

    assert to_create[1].path == "A/f"

    assert files[0].name == "B"
    assert files[0].path == "A/B"
    assert files[1].name == "f"
    assert files[1].path == "A/f"
    assert len(files) == 2


async def test_create_batch_but_file_already_exists(
    db_pool: DBPool,
    namespace: Namespace,
):
    file = await crud.file.create(db_pool, namespace.path, "f")

    with pytest.raises(errors.FileAlreadyExists):
        await crud.file.create_batch(db_pool, namespace.path, ".", files=[file])


async def test_create_batch_but_no_files_given():
    # pass dummy DBPool, to check that method exists earlier with empty files
    result = await crud.file.create_batch(
        object(),  # type: ignore
        "namespace",
        ".",
        files=[],
    )
    assert result is None


async def test_create_batch_but_parent_not_exists(
    db_pool: DBPool,
    namespace: Namespace,
):
    file = File.construct()  # type: ignore

    with pytest.raises(errors.FileNotFound):
        await crud.file.create_batch(db_pool, namespace.path, "a", files=[file])


async def test_create_batch_but_parent_not_a_folder(
    db_pool: DBPool,
    namespace: Namespace,
):
    file = File.construct()  # type: ignore
    await crud.file.create(db_pool, namespace.path, "f")

    with pytest.raises(errors.NotADirectory):
        await crud.file.create_batch(db_pool, namespace.path, "f", files=[file])


async def test_create_folder(db_pool: DBPool, namespace: Namespace):
    path = Path("a/b/c")
    await crud.file.create_folder(db_pool, namespace.path, path)

    query = """
        SELECT File { id, path, parent: { id } }
        FILTER
            str_lower(.path) IN array_unpack(<array<str>>$paths)
            AND
            .namespace.path = <str>$namespace
        ORDER BY str_lower(.path) ASC
    """

    paths = [str(path)] + [str(p) for p in path.parents]
    result = await db_pool.query(query, namespace=str(namespace.path), paths=paths)

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
    db_pool: DBPool,
    namespace: Namespace,
):
    paths = [
        Path("a/b"),
        Path("a/b/c/d"),
        Path("a/b/c/d/e/f/g"),
        Path("a/b/c/d/c"),
    ]

    await asyncio.gather(*(
        crud.file.create_folder(db_pool, namespace.path, path)
        for path in paths
    ))

    files = list(await db_pool.query("""
        SELECT File { id, path, parent: { id } }
        FILTER
            str_lower(.path) != 'trash'
            AND
            .namespace.path = <str>$namespace
        ORDER BY str_lower(.path) ASC
    """, namespace=str(namespace.path)))

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


async def test_create_folder_is_case_insensitive(db_pool: DBPool, namespace: Namespace):
    await crud.file.create_folder(db_pool, namespace.path, "A/b")
    await crud.file.create_folder(db_pool, namespace.path, "a/B/c")

    query = """
        SELECT File { id, path, parent: { id } }
        FILTER
            str_lower(.path) IN array_unpack(<array<str>>$paths)
            AND
            .namespace.path = <str>$namespace
        ORDER BY str_lower(.path) ASC
    """

    paths = ["a", "a/b", "a/b/c"]
    a, b, c = await db_pool.query(query, namespace=str(namespace.path), paths=paths)

    assert a.path == "A"
    assert b.path == "A/b"
    assert c.path == "A/b/c"


@pytest.mark.parametrize(["a", "b"], [
    ("folder", "folder"),
    ("Folder", "folder"),
])
async def test_create_folder_but_folder_exists(
    db_pool: DBPool,
    namespace: Namespace,
    a: str,
    b: str,
):
    await crud.file.create_folder(db_pool, namespace.path, a)

    with pytest.raises(errors.FileAlreadyExists):
        await crud.file.create_folder(db_pool, namespace.path, b)


async def test_create_folder_but_path_is_not_a_directory(
    db_pool: DBPool,
    namespace: Namespace,
):
    await crud.file.create(db_pool, namespace.path, "data")

    with pytest.raises(errors.NotADirectory):
        await crud.file.create_folder(db_pool, namespace.path, "data/file")


async def test_delete_file(db_pool: DBPool, namespace: Namespace):
    path = Path("folder/file")
    await crud.file.create(db_pool, namespace.path, path.parent, mediatype=FOLDER)
    await crud.file.create(db_pool, namespace.path, path.parent / "b", size=4)
    await crud.file.create(db_pool, namespace.path, path, size=8)

    # ensure parent size has increased
    parent = await crud.file.get(db_pool, namespace.path, path.parent)
    assert parent.size == 12

    file = await crud.file.delete(db_pool, namespace.path, path)
    assert file.path == str(path)
    assert not await crud.file.exists(db_pool, namespace.path, path)

    # ensure parent size has decreased
    parent = await crud.file.get(db_pool, namespace.path, path.parent)
    assert parent.size == 4


async def test_delete_non_empty_folder(db_pool: DBPool, namespace: Namespace):
    await crud.file.create(db_pool, namespace.path, "a", mediatype=FOLDER)
    await crud.file.create(db_pool, namespace.path, "a/b", mediatype=FOLDER)
    await crud.file.create(db_pool, namespace.path, "a/b/c", size=8)

    # ensure parent size has increased
    a, b = await crud.file.get_many(db_pool, namespace.path, ["a", "a/b"])
    assert a.size == 8
    assert b.size == 8

    await crud.file.delete(db_pool, namespace.path, "a/b")
    assert not await crud.file.exists(db_pool, namespace.path, "a/b")
    assert not await crud.file.exists(db_pool, namespace.path, "a/b/c")

    # ensure size has decreased
    parent = await crud.file.get(db_pool, namespace.path, "a")
    assert parent.size == 0


async def test_delete_is_case_insensitive(db_pool: DBPool, namespace: Namespace):
    await crud.file.create(db_pool, namespace.path, "F", size=8)

    file = await crud.file.delete(db_pool, namespace.path, "f")
    assert file.path == "F"


async def test_delete_file_but_it_does_not_exist(db_pool: DBPool, namespace: Namespace):
    with pytest.raises(errors.FileNotFound):
        await crud.file.delete(db_pool, namespace.path, "f")


async def test_delete_batch(db_pool: DBPool, namespace: Namespace):
    await crud.file.create(db_pool, namespace.path, "a", mediatype=FOLDER)
    await crud.file.create(db_pool, namespace.path, "a/B", mediatype=FOLDER)
    await crud.file.create(db_pool, namespace.path, "a/B/c", size=8)
    await crud.file.create(db_pool, namespace.path, "a/f", size=16)

    # ensure parent size has increased
    a, b = await crud.file.get_many(db_pool, namespace.path, ["a", "a/b"])
    assert a.size == 24
    assert b.size == 8

    await crud.file.delete_batch(db_pool, namespace.path, "A", ["B", "f"])
    assert not await crud.file.exists(db_pool, namespace.path, "a/b")
    assert not await crud.file.exists(db_pool, namespace.path, "a/b/c")
    assert not await crud.file.exists(db_pool, namespace.path, "a/f")

    # ensure size has decreased
    parent = await crud.file.get(db_pool, namespace.path, "a")
    assert parent.size == 0


async def test_empty_trash(db_pool: DBPool, namespace: Namespace):
    await crud.file.create_folder(db_pool, namespace.path, "Trash/a/b")
    await crud.file.create_folder(db_pool, namespace.path, "Trash/a/c")
    await crud.file.create(db_pool, namespace.path, "Trash/f", size=32)
    await crud.file.create(db_pool, namespace.path, "f", size=16)

    home = await crud.file.get(db_pool, namespace.path, ".")
    assert home.size == 48

    trash = await crud.file.empty_trash(db_pool, namespace.path)

    assert await crud.file.get(db_pool, namespace.path, "Trash") == trash
    files = await crud.file.list_folder(db_pool, namespace.path, "Trash")
    assert trash.size == 0
    assert files == []

    home = await crud.file.get(db_pool, namespace.path, ".")
    assert home.size == 16


async def test_empty_trash_but_its_already_empty(db_pool: DBPool, namespace: Namespace):
    trash = await crud.file.empty_trash(db_pool, namespace.path)
    files = await crud.file.list_folder(db_pool, namespace.path, "Trash")
    assert trash.size == 0
    assert files == []


@pytest.mark.parametrize(["a", "b"], [
    ("file", "file"),
    ("File", "file"),
    ("file", "File"),
])
async def test_exists(db_pool: DBPool, namespace: Namespace, a, b):
    await crud.file.create(db_pool, namespace.path, a)
    assert await crud.file.exists(db_pool, namespace.path, b)


async def test_exists_but_it_is_not(db_pool: DBPool, namespace: Namespace):
    assert not await crud.file.exists(db_pool, namespace.path, "file")


@pytest.mark.parametrize(["a", "b"], [
    ("file", "file"),
    ("File", "file"),
    ("file", "File"),
])
async def test_get(db_pool: DBPool, namespace: Namespace, a, b):
    await crud.file.create(db_pool, namespace.path, a)
    file = await crud.file.get(db_pool, namespace.path, b)
    assert file.name == a
    assert file.path == a


async def test_get_but_file_does_not_exists(db_pool: DBPool, namespace: Namespace):
    with pytest.raises(errors.FileNotFound):
        await crud.file.get(db_pool, namespace.path, "file")


async def test_get_many(db_pool: DBPool, namespace: Namespace):
    await crud.file.create(db_pool, namespace.path, "a", mediatype=FOLDER)
    await crud.file.create(db_pool, namespace.path, "a/b", mediatype=FOLDER)
    await crud.file.create(db_pool, namespace.path, "a/c", mediatype=FOLDER)
    await crud.file.create(db_pool, namespace.path, "a/f")

    paths = ["a", "a/c", "a/f", "a/d"]
    files = await crud.file.get_many(db_pool, namespace.path, paths=paths)

    assert len(files) == 3
    for file, path in zip(files, paths[:-1]):
        assert file.path == path


async def test_get_many_is_case_insensitive(db_pool: DBPool, namespace: Namespace):
    await crud.file.create(db_pool, namespace.path, "a", mediatype=FOLDER)
    await crud.file.create(db_pool, namespace.path, "a/B", mediatype=FOLDER)
    await crud.file.create(db_pool, namespace.path, "a/c", mediatype=FOLDER)
    await crud.file.create(db_pool, namespace.path, "A/F")

    paths = ["A", "a/C", "a/f", "a/d"]
    files = await crud.file.get_many(db_pool, namespace.path, paths=paths)

    assert files[0].path == "a"
    assert files[1].path == "a/c"
    assert files[2].path == "a/F"

    assert len(files) == 3


async def test_list_folder(db_pool: DBPool, namespace: Namespace):
    await crud.file.create_folder(db_pool, namespace.path, "a/c")
    await crud.file.create(db_pool, namespace.path, "a/b")
    files = await crud.file.list_folder(db_pool, namespace.path, "a")
    assert len(files) == 2
    assert files[0].path == "a/c"  # folders listed first
    assert files[1].path == "a/b"


async def test_list_folder_excluding_trash(db_pool: DBPool, namespace: Namespace):
    files = await crud.file.list_folder(db_pool, namespace.path, ".")
    assert files == []


async def test_list_home_with_trash(db_pool: DBPool, namespace: Namespace):
    files = await crud.file.list_folder(db_pool, namespace.path, ".", with_trash=True)
    assert files[0].path == "Trash"


async def test_list_folder_is_case_insensitive(db_pool: DBPool, namespace: Namespace):
    await crud.file.create_folder(db_pool, namespace.path, "A/b")
    await crud.file.create_folder(db_pool, namespace.path, "A/C")
    await crud.file.create(db_pool, namespace.path, "a/F")
    files = await crud.file.list_folder(db_pool, namespace.path, "A")
    assert files[0].path == "A/b"  # folders listed first
    assert files[1].path == "A/C"
    assert files[2].path == "A/F"
    assert len(files) == 3


async def test_list_folder_but_it_is_empty(db_pool: DBPool, namespace: Namespace):
    await crud.file.create_folder(db_pool, namespace.path, "a")
    files = await crud.file.list_folder(db_pool, namespace.path, "a")
    assert files == []


async def test_list_folder_but_it_not_found(db_pool: DBPool, namespace: Namespace):
    with pytest.raises(errors.FileNotFound):
        await crud.file.list_folder(db_pool, namespace.path, "a")


async def test_list_folder_but_it_a_file(db_pool: DBPool, namespace: Namespace):
    await crud.file.create(db_pool, namespace.path, "f")
    with pytest.raises(errors.NotADirectory):
        await crud.file.list_folder(db_pool, namespace.path, "f")


async def test_move(db_pool: DBPool, namespace: Namespace):
    await crud.file.create_folder(db_pool, namespace.path, "a/b/c")
    await crud.file.create(db_pool, namespace.path, "a/b/c/f", size=24)
    await crud.file.create(db_pool, namespace.path, "a/g", size=8, mediatype=FOLDER)

    # move folder 'c' from 'a/b' to 'a/g'
    await crud.file.move(db_pool, namespace.path, "a/b/c", "a/g/c")

    assert not await crud.file.exists(db_pool, namespace.path, "a/b/c")

    query = """
        SELECT File { size, parent: { id } }
        FILTER
            .path IN array_unpack(<array<str>>$paths)
            AND
            .namespace.path = <str>$ns_path
        ORDER BY .path ASC
    """

    paths = ["a", "a/b", "a/g", "a/g/c", "a/g/c/f"]
    a, b, g, c, f = await db_pool.query(query, ns_path=str(namespace.path), paths=paths)

    assert b.size == 0
    assert b.parent.id == a.id

    assert g.size == 32
    assert g.parent.id == a.id

    assert c.size == 24
    assert c.parent.id == g.id

    assert f.size == 24
    assert f.parent.id == c.id


async def test_move_with_renaming(db_pool: DBPool, namespace: Namespace):
    await crud.file.create(db_pool, namespace.path, "a", mediatype=FOLDER)
    await crud.file.create(db_pool, namespace.path, "a/f")

    # rename file 'f' to 'f.txt'
    await crud.file.move(db_pool, namespace.path, "a/f", "a/f.txt")

    assert not await crud.file.exists(db_pool, namespace.path, "a/f")

    f = await crud.file.get(db_pool, namespace.path, "a/f.txt")
    assert f.name == "f.txt"


async def test_move_file_is_case_insensitive(db_pool: DBPool, namespace: Namespace):
    await crud.file.create(db_pool, namespace.path, "a", mediatype=FOLDER)
    await crud.file.create(db_pool, namespace.path, "a/B", mediatype=FOLDER)
    await crud.file.create(db_pool, namespace.path, "a/f", size=8)

    # move file from 'a/f' to 'a/B/F.TXT'
    await crud.file.move(db_pool, namespace.path, "A/F", "A/b/F.TXT")

    assert not await crud.file.exists(db_pool, namespace.path, "a/f")

    f = await crud.file.get(db_pool, namespace.path, "a/b/f.txt")
    assert f.name == "F.TXT"
    assert f.path == "a/B/F.TXT"

    a, b = await crud.file.get_many(db_pool, namespace.path, ["a", "a/b"])
    assert a.size == 8
    assert b.size == 8


async def test_move_folder_is_case_insensitive(db_pool: DBPool, namespace: Namespace):
    await crud.file.create(db_pool, namespace.path, "a", mediatype=FOLDER)
    await crud.file.create(db_pool, namespace.path, "a/B", mediatype=FOLDER)
    await crud.file.create(db_pool, namespace.path, "a/B/f", size=8)
    await crud.file.create(db_pool, namespace.path, "a/c", mediatype=FOLDER)

    # move folder from 'a/B' to 'a/c/b'
    await crud.file.move(db_pool, namespace.path, "A/b", "A/C/b")

    assert not await crud.file.exists(db_pool, namespace.path, "a/b")

    a = await crud.file.get(db_pool, namespace.path, "a")
    assert a.size == 8

    b = await crud.file.get(db_pool, namespace.path, "a/c/b")
    assert b.name == "b"
    assert b.path == "a/c/b"

    c = await crud.file.get(db_pool, namespace.path, "a/c")
    assert c.size == 8

    f = await crud.file.get(db_pool, namespace.path, "a/c/b/f")
    assert f.path == "a/c/b/f"


async def test_move_but_next_path_is_already_taken(
    db_pool: DBPool,
    namespace: Namespace,
):
    await crud.file.create_folder(db_pool, namespace.path, "a/b")
    await crud.file.create_folder(db_pool, namespace.path, "a/c")

    with pytest.raises(errors.FileAlreadyExists):
        await crud.file.move(db_pool, namespace.path, "a/b", "a/c")

    with pytest.raises(errors.FileAlreadyExists):
        await crud.file.move(db_pool, namespace.path, "A/B", "A/C")


async def test_move_but_from_path_that_does_not_exists(
    db_pool: DBPool,
    namespace: Namespace,
):
    with pytest.raises(errors.FileNotFound):
        await crud.file.move(db_pool, namespace.path, "f", "a")


async def test_move_but_next_path_has_missing_parent(
    db_pool: DBPool,
    namespace: Namespace,
):
    await crud.file.create(db_pool, namespace.path, "f")

    with pytest.raises(errors.FileNotFound):
        await crud.file.move(db_pool, namespace.path, "f", "a/f")


async def test_move_but_next_path_is_not_a_folder(
    db_pool: DBPool,
    namespace: Namespace,
):
    await crud.file.create(db_pool, namespace.path, "a")
    await crud.file.create(db_pool, namespace.path, "f")

    with pytest.raises(errors.NotADirectory):
        await crud.file.move(db_pool, namespace.path, "a", "f/a")


@pytest.mark.parametrize(["name", "next_name"], [
    ("f.txt", "f (1).txt"),
    ("f.tar.gz", "f (1).tar.gz"),
    ("f (1).tar.gz", "f (1) (1).tar.gz"),
])
async def test_next_path(db_pool: DBPool, namespace: Namespace, name, next_name):
    await crud.file.create_folder(db_pool, namespace.path, "a/b")
    await crud.file.create(db_pool, namespace.path, f"a/b/{name}")

    next_path = await crud.file.next_path(db_pool, namespace.path, f"a/b/{name}")
    assert next_path == f"a/b/{next_name}"
    assert not await crud.file.exists(db_pool, namespace.path, next_name)


async def test_next_path_is_sequential(db_pool: DBPool, namespace: Namespace):
    await crud.file.create(db_pool, namespace.path, "f.tar.gz")
    await crud.file.create(db_pool, namespace.path, "f (1).tar.gz")

    next_path = await crud.file.next_path(db_pool, namespace.path, "f.tar.gz")
    assert next_path == "f (2).tar.gz"
    assert not await crud.file.exists(db_pool, namespace.path, "f (2).tar.gz")


async def test_next_path_is_case_insensitive(db_pool: DBPool, namespace: Namespace):
    await crud.file.create(db_pool, namespace.path, "F.TAR.GZ")
    await crud.file.create(db_pool, namespace.path, "F (1).tar.gz")

    next_path = await crud.file.next_path(db_pool, namespace.path, "f.tar.gz")
    assert next_path == "f (2).tar.gz"
    assert not await crud.file.exists(db_pool, namespace.path, "f (2).tar.gz")


async def test_inc_size_batch(db_pool: DBPool, namespace: Namespace):
    await crud.file.create_folder(db_pool, namespace.path, "a/b")
    await crud.file.create_folder(db_pool, namespace.path, "a/c")

    await crud.file.inc_size_batch(db_pool, namespace.path, paths=["a", "a/c"], size=16)

    paths = ["a", "a/b", "a/c"]
    a, b, c = await crud.file.get_many(db_pool, namespace.path, paths=paths)
    assert a.size == 16
    assert b.size == 0
    assert c.size == 16


async def test_inc_size_batch_is_case_insensitive(
    db_pool: DBPool,
    namespace: Namespace,
):
    await crud.file.create_folder(db_pool, namespace.path, "a/b")
    await crud.file.create_folder(db_pool, namespace.path, "a/C")

    await crud.file.inc_size_batch(db_pool, namespace.path, paths=["A", "A/c"], size=16)

    paths = ["a", "a/b", "a/c"]
    a, b, c = await crud.file.get_many(db_pool, namespace.path, paths=paths)
    assert a.size == 16
    assert b.size == 0
    assert c.size == 16


async def test_inc_size_batch_but_size_is_zero():
    # pass dummy DBPool, to check that method exists earlier with empty files
    result = await crud.file.inc_size_batch(
        object(),  # type: ignore
        "namespace",
        paths=["a/b"],
        size=0,
    )
    assert result is None
