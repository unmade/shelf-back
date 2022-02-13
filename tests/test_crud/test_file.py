from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from app import crud, errors
from app.entities import File
from app.mediatypes import FOLDER, OCTET_STREAM

if TYPE_CHECKING:
    from app.entities import Namespace
    from app.typedefs import DBClient, DBTransaction
    from tests.factories import FileFactory, MediaTypeFactory, NamespaceFactory

pytestmark = [pytest.mark.asyncio, pytest.mark.database]


async def test_create(tx: DBTransaction, namespace: Namespace):
    path = Path("a/b/f")
    for parent in list(reversed(path.parents))[1:]:
        await crud.file.create(tx, namespace.path, parent, mediatype=FOLDER)

    folder = await crud.file.get(tx, namespace.path, path.parent)
    assert folder.size == 0

    await crud.file.create(tx, namespace.path, path, size=32)

    a, b, f = await tx.query("""
        SELECT
            File {
                name, path, size, mediatype: { name },
            }
        FILTER
            .namespace.path = <str>$namespace
            AND
            .path IN {array_unpack(<array<str>>$paths)}
        ORDER BY
            .path
    """, namespace=str(namespace.path), paths=["a", "a/b", "a/b/f"])

    assert f.name == path.name
    assert f.path == str(path)
    assert f.size == 32
    assert f.mediatype.name == OCTET_STREAM
    assert b.path == str(path.parent)
    assert b.mediatype.name == FOLDER
    assert a.path == str(path.parent.parent)
    assert a.size == 32


async def test_create_updates_parents_size(tx: DBTransaction, namespace: Namespace):
    path = Path("New Folder/file")
    await crud.file.create(tx, namespace.path, path.parent, mediatype=FOLDER)
    await crud.file.create(tx, namespace.path, path, size=32)

    parents = await crud.file.get_many(tx, namespace.path, path.parents)
    for parent in parents:
        assert parent.size == 32


async def test_create_is_case_insensitive(tx: DBTransaction, namespace: Namespace):
    await crud.file.create(tx, namespace.path, "A", mediatype=FOLDER)
    await crud.file.create(tx, namespace.path, "a/f", size=32)

    file = await crud.file.get(tx, namespace.path, "a/f")
    assert file.path == "A/f"  # original case of parent is preserved


async def test_create_but_parent_is_missing(tx: DBTransaction, namespace: Namespace):
    with pytest.raises(errors.MissingParent):
        await crud.file.create(tx, namespace.path, "New Folder/file")


async def test_create_but_parent_is_not_a_folder(
    tx: DBTransaction,
    namespace: Namespace,
):
    await crud.file.create(tx, namespace.path, "f")

    with pytest.raises(errors.NotADirectory):
        await crud.file.create(tx, namespace.path, "f/a")


async def test_create_but_file_already_exists(tx: DBTransaction, namespace: Namespace):
    with pytest.raises(errors.FileAlreadyExists):
        await crud.file.create(tx, namespace.path, ".")


async def test_create_batch(
    tx: DBTransaction, namespace: Namespace, mediatype_factory: MediaTypeFactory,
):
    await mediatype_factory(FOLDER)
    await mediatype_factory(OCTET_STREAM)

    a_size, f_size = 32, 16
    files = [
        File(
            id=None,  # type: ignore
            name="a",
            path="a",
            size=a_size,
            mtime=time.time(),
            mediatype=FOLDER,
        ),
        File(
            id=None,  # type: ignore
            name="f",
            path="f",
            size=f_size,
            mtime=time.time(),
            mediatype=OCTET_STREAM,
        )
    ]
    await crud.file.create_batch(tx, namespace.path, files=files)

    home = await crud.file.get(tx, namespace.path, ".")
    assert home.size == 0

    files = await crud.file.list_folder(tx, namespace.path, ".")
    assert len(files) == 2

    assert files[0].name == "a"
    assert files[0].size == a_size
    assert files[0].is_folder() is True
    assert files[0].mediatype == FOLDER

    assert files[1].name == "f"
    assert files[1].size == f_size
    assert files[1].is_folder() is False
    assert files[1].mediatype == OCTET_STREAM


async def test_create_batch_is_case_sensitive(
    tx: DBTransaction,
    namespace: Namespace,
    mediatype_factory: MediaTypeFactory,
):
    await mediatype_factory(FOLDER)
    await mediatype_factory(OCTET_STREAM)

    await crud.file.create(tx, namespace.path, "A", mediatype=FOLDER)

    to_create = [
        File(
            id=None,  # type: ignore
            name="B",
            path="A/B",
            size=0,
            mtime=time.time(),
            mediatype=FOLDER,
        ),
        File(
            id=None,  # type: ignore
            name="f",
            path="a/f",
            size=8,
            mtime=time.time(),
            mediatype=OCTET_STREAM,
        )
    ]

    await crud.file.create_batch(tx, namespace.path, files=to_create)
    assert to_create[1].path == "a/f"

    files = await crud.file.list_folder(tx, namespace.path, "A")
    assert len(files) == 1
    assert files[0].name == "B"
    assert files[0].path == "A/B"

    file = await crud.file.get(tx, namespace.path, "a/f")
    assert file.name == "f"
    assert file.path == "a/f"


async def test_create_batch_but_file_already_exists(
    tx: DBTransaction,
    namespace: Namespace,
):
    file = await crud.file.create(tx, namespace.path, "f")

    with pytest.raises(errors.FileAlreadyExists):
        await crud.file.create_batch(tx, namespace.path, files=[file])


async def test_create_batch_but_no_files_given():
    # pass dummy DBTransaction, to check that method exists earlier with empty files
    result = await crud.file.create_batch(
        object(),  # type: ignore
        "namespace",
        files=[],
    )
    assert result is None


async def test_create_folder(tx: DBTransaction, namespace: Namespace):
    path = Path("a/b/c")
    await crud.file.create_folder(tx, namespace.path, path)

    query = """
        SELECT File { id, path }
        FILTER
            str_lower(.path) IN array_unpack(<array<str>>$paths)
            AND
            .namespace.path = <str>$namespace
        ORDER BY str_lower(.path) ASC
    """

    paths = [str(path)] + [str(p) for p in path.parents]
    result = await tx.query(query, namespace=str(namespace.path), paths=paths)

    home, a, b, c = result
    assert home.path == "."
    assert a.path == "a"
    assert b.path == "a/b"
    assert c.path == "a/b/c"


@pytest.mark.database(transaction=True)
async def test_create_folder_concurrently_with_overlapping_parents(
    db_client: DBClient,
    namespace: Namespace,
):
    paths = [
        Path("a/b"),
        Path("a/b/c/d"),
        Path("a/b/c/d/e/f/g"),
        Path("a/b/c/d/c"),
    ]

    await asyncio.gather(*(
        crud.file.create_folder(db_client, namespace.path, path)
        for path in paths
    ))

    files = await db_client.query("""
        SELECT File { id, path }
        FILTER
            str_lower(.path) != 'trash'
            AND
            .namespace.path = <str>$namespace
        ORDER BY str_lower(.path) ASC
    """, namespace=str(namespace.path))

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


async def test_create_folder_is_case_insensitive(
    tx: DBTransaction,
    namespace: Namespace,
):
    await crud.file.create_folder(tx, namespace.path, "A/b")
    await crud.file.create_folder(tx, namespace.path, "a/B/c")

    query = """
        SELECT File { id, path }
        FILTER
            str_lower(.path) IN array_unpack(<array<str>>$paths)
            AND
            .namespace.path = <str>$namespace
        ORDER BY str_lower(.path) ASC
    """

    paths = ["a", "a/b", "a/b/c"]
    a, b, c = await tx.query(query, namespace=str(namespace.path), paths=paths)

    assert a.path == "A"
    assert b.path == "A/b"
    assert c.path == "A/b/c"


@pytest.mark.parametrize(["a", "b"], [
    ("folder", "folder"),
    ("Folder", "folder"),
])
async def test_create_folder_but_folder_exists(
    tx: DBTransaction,
    namespace: Namespace,
    a: str,
    b: str,
):
    await crud.file.create_folder(tx, namespace.path, a)

    with pytest.raises(errors.FileAlreadyExists):
        await crud.file.create_folder(tx, namespace.path, b)


async def test_create_folder_but_path_is_not_a_directory(
    tx: DBTransaction,
    namespace: Namespace,
):
    await crud.file.create(tx, namespace.path, "data")

    with pytest.raises(errors.NotADirectory):
        await crud.file.create_folder(tx, namespace.path, "data/file")


async def test_create_home_folder(tx: DBTransaction, namespace: Namespace):
    await tx.execute("DELETE File;")
    home = await crud.file.create_home_folder(tx, namespace.path)
    assert home.name == namespace.path.name
    assert home.path == "."
    assert home.size == 0
    assert home.mediatype == FOLDER


async def test_create_home_folder_but_it_already_exists(
    tx: DBTransaction,
    namespace: Namespace,
):
    with pytest.raises(errors.FileAlreadyExists):
        await crud.file.create_home_folder(tx, namespace.path)


async def test_delete_file(tx: DBTransaction, namespace: Namespace):
    path = Path("folder/file")
    await crud.file.create(tx, namespace.path, path.parent, mediatype=FOLDER)
    await crud.file.create(tx, namespace.path, path.parent / "b", size=4)
    await crud.file.create(tx, namespace.path, path, size=8)

    # ensure parent size has increased
    parent = await crud.file.get(tx, namespace.path, path.parent)
    assert parent.size == 12

    file = await crud.file.delete(tx, namespace.path, path)
    assert file.path == str(path)
    assert not await crud.file.exists(tx, namespace.path, path)

    # ensure parent size has decreased
    parent = await crud.file.get(tx, namespace.path, path.parent)
    assert parent.size == 4


async def test_delete_non_empty_folder(tx: DBTransaction, namespace: Namespace):
    await crud.file.create(tx, namespace.path, "a", mediatype=FOLDER)
    await crud.file.create(tx, namespace.path, "a/b", mediatype=FOLDER)
    await crud.file.create(tx, namespace.path, "a/b/c", size=8)

    # ensure parent size has increased
    a, b = await crud.file.get_many(tx, namespace.path, ["a", "a/b"])
    assert a.size == 8
    assert b.size == 8

    await crud.file.delete(tx, namespace.path, "a/b")
    assert not await crud.file.exists(tx, namespace.path, "a/b")
    assert not await crud.file.exists(tx, namespace.path, "a/b/c")

    # ensure size has decreased
    parent = await crud.file.get(tx, namespace.path, "a")
    assert parent.size == 0


async def test_delete_is_case_insensitive(tx: DBTransaction, namespace: Namespace):
    await crud.file.create(tx, namespace.path, "F", size=8)

    file = await crud.file.delete(tx, namespace.path, "f")
    assert file.path == "F"


async def test_delete_file_but_it_does_not_exist(
    tx: DBTransaction,
    namespace: Namespace,
):
    with pytest.raises(errors.FileNotFound):
        await crud.file.delete(tx, namespace.path, "f")


async def test_empty_trash(tx: DBTransaction, namespace: Namespace):
    await crud.file.create_folder(tx, namespace.path, "Trash/a/b")
    await crud.file.create_folder(tx, namespace.path, "Trash/a/c")
    await crud.file.create(tx, namespace.path, "Trash/f", size=32)
    await crud.file.create(tx, namespace.path, "f", size=16)

    home = await crud.file.get(tx, namespace.path, ".")
    assert home.size == 48

    trash = await crud.file.empty_trash(tx, namespace.path)

    assert await crud.file.get(tx, namespace.path, "Trash") == trash
    files = await crud.file.list_folder(tx, namespace.path, "Trash")
    assert trash.size == 0
    assert files == []

    home = await crud.file.get(tx, namespace.path, ".")
    assert home.size == 16


async def test_empty_trash_but_its_already_empty(
    tx: DBTransaction,
    namespace: Namespace,
):
    trash = await crud.file.empty_trash(tx, namespace.path)
    files = await crud.file.list_folder(tx, namespace.path, "Trash")
    assert trash.size == 0
    assert files == []


@pytest.mark.parametrize(["a", "b"], [
    ("file", "file"),
    ("File", "file"),
    ("file", "File"),
])
async def test_exists(tx: DBTransaction, namespace: Namespace, a, b):
    await crud.file.create(tx, namespace.path, a)
    assert await crud.file.exists(tx, namespace.path, b)


async def test_exists_but_it_is_not(tx: DBTransaction, namespace: Namespace):
    assert not await crud.file.exists(tx, namespace.path, "file")


@pytest.mark.parametrize(["a", "b"], [
    ("file", "file"),
    ("File", "file"),
    ("file", "File"),
])
async def test_get(tx: DBTransaction, namespace: Namespace, a, b):
    await crud.file.create(tx, namespace.path, a)
    file = await crud.file.get(tx, namespace.path, b)
    assert file.name == a
    assert file.path == a


async def test_get_but_file_does_not_exist(tx: DBTransaction, namespace: Namespace):
    with pytest.raises(errors.FileNotFound):
        await crud.file.get(tx, namespace.path, "file")


async def test_get_by_id(tx: DBTransaction, namespace: Namespace):
    file = await crud.file.create(tx, namespace.path, "f.txt")
    result = await crud.file.get_by_id(tx, file.id)
    assert result == file


async def test_get_by_id_but_file_does_not_exist(
    tx: DBTransaction,
    namespace: Namespace,
):
    file_id = uuid.uuid4()
    with pytest.raises(errors.FileNotFound):
        await crud.file.get_by_id(tx, file_id)


async def test_get_by_id_batch(
    tx: DBTransaction,
    namespace: Namespace,
    file_factory: FileFactory,
):
    files = [await file_factory(namespace.path) for _ in range(7)]
    ids = [file.id for file in files[::2]]
    files = await crud.file.get_by_id_batch(tx, namespace.path, ids=ids)
    assert len(files) == len(ids)
    assert set(f.id for f in files) == set(ids)


async def test_get_by_id_batch_filters_only_by_ids_in_namespace(
    tx: DBTransaction,
    namespace_factory: NamespaceFactory,
    file_factory: FileFactory,
):
    namespace_a = await namespace_factory()
    namespace_b = await namespace_factory()
    files_a = [await file_factory(namespace_a.path) for _ in range(2)]
    files_b = [await file_factory(namespace_b.path) for _ in range(2)]
    ids = [file.id for file in files_a] + [file.id for file in files_b]
    files = await crud.file.get_by_id_batch(tx, namespace_a.path, ids=ids)
    assert set(f.id for f in files) == set(f.id for f in files_a)


async def test_get_many(tx: DBTransaction, namespace: Namespace):
    await crud.file.create(tx, namespace.path, "a", mediatype=FOLDER)
    await crud.file.create(tx, namespace.path, "a/b", mediatype=FOLDER)
    await crud.file.create(tx, namespace.path, "a/c", mediatype=FOLDER)
    await crud.file.create(tx, namespace.path, "a/f")

    paths = ["a", "a/c", "a/f", "a/d"]
    files = await crud.file.get_many(tx, namespace.path, paths=paths)

    assert len(files) == 3
    for file, path in zip(files, paths[:-1]):
        assert file.path == path


async def test_get_many_is_case_insensitive(tx: DBTransaction, namespace: Namespace):
    await crud.file.create(tx, namespace.path, "a", mediatype=FOLDER)
    await crud.file.create(tx, namespace.path, "a/B", mediatype=FOLDER)
    await crud.file.create(tx, namespace.path, "a/c", mediatype=FOLDER)
    await crud.file.create(tx, namespace.path, "A/F")

    paths = ["A", "a/C", "a/f", "a/d"]
    files = await crud.file.get_many(tx, namespace.path, paths=paths)

    assert files[0].path == "a"
    assert files[1].path == "a/c"
    assert files[2].path == "a/F"

    assert len(files) == 3


async def test_list_folder(tx: DBTransaction, namespace: Namespace):
    await crud.file.create_folder(tx, namespace.path, "a/c")
    await crud.file.create(tx, namespace.path, "a/b")
    files = await crud.file.list_folder(tx, namespace.path, "a")
    assert len(files) == 2
    assert files[0].path == "a/c"  # folders listed first
    assert files[1].path == "a/b"


async def test_list_folder_excluding_trash(tx: DBTransaction, namespace: Namespace):
    files = await crud.file.list_folder(tx, namespace.path, ".")
    assert files == []


async def test_list_home_with_trash(tx: DBTransaction, namespace: Namespace):
    files = await crud.file.list_folder(tx, namespace.path, ".", with_trash=True)
    assert files[0].path == "Trash"


async def test_list_folder_is_case_insensitive(tx: DBTransaction, namespace: Namespace):
    await crud.file.create_folder(tx, namespace.path, "A/b")
    await crud.file.create_folder(tx, namespace.path, "A/C")
    await crud.file.create(tx, namespace.path, "a/F")
    files = await crud.file.list_folder(tx, namespace.path, "A")
    assert files[0].path == "A/b"  # folders listed first
    assert files[1].path == "A/C"
    assert files[2].path == "A/F"
    assert len(files) == 3


async def test_list_folder_but_it_is_empty(tx: DBTransaction, namespace: Namespace):
    await crud.file.create_folder(tx, namespace.path, "a")
    files = await crud.file.list_folder(tx, namespace.path, "a")
    assert files == []


async def test_list_folder_but_it_not_found(tx: DBTransaction, namespace: Namespace):
    with pytest.raises(errors.FileNotFound):
        await crud.file.list_folder(tx, namespace.path, "a")


async def test_list_folder_but_it_a_file(tx: DBTransaction, namespace: Namespace):
    await crud.file.create(tx, namespace.path, "f")
    with pytest.raises(errors.NotADirectory):
        await crud.file.list_folder(tx, namespace.path, "f")


async def test_move(tx: DBTransaction, namespace: Namespace):
    await crud.file.create_folder(tx, namespace.path, "a/b/c")
    await crud.file.create(tx, namespace.path, "a/b/c/f", size=24)
    await crud.file.create(tx, namespace.path, "a/g", size=8, mediatype=FOLDER)

    # move folder 'c' from 'a/b' to 'a/g'
    await crud.file.move(tx, namespace.path, "a/b/c", "a/g/c")

    assert not await crud.file.exists(tx, namespace.path, "a/b/c")

    query = """
        SELECT File { size }
        FILTER
            .path IN array_unpack(<array<str>>$paths)
            AND
            .namespace.path = <str>$ns_path
        ORDER BY .path ASC
    """

    paths = ["a", "a/b", "a/g", "a/g/c", "a/g/c/f"]
    a, b, g, c, f = await tx.query(query, ns_path=str(namespace.path), paths=paths)

    assert b.size == 0
    assert g.size == 32
    assert c.size == 24
    assert f.size == 24


async def test_move_with_renaming(tx: DBTransaction, namespace: Namespace):
    await crud.file.create(tx, namespace.path, "a", mediatype=FOLDER)
    await crud.file.create(tx, namespace.path, "a/f")

    # rename file 'f' to 'f.txt'
    await crud.file.move(tx, namespace.path, "a/f", "a/f.txt")

    assert not await crud.file.exists(tx, namespace.path, "a/f")

    f = await crud.file.get(tx, namespace.path, "a/f.txt")
    assert f.name == "f.txt"


async def test_move_file_is_case_insensitive(tx: DBTransaction, namespace: Namespace):
    await crud.file.create(tx, namespace.path, "a", mediatype=FOLDER)
    await crud.file.create(tx, namespace.path, "a/B", mediatype=FOLDER)
    await crud.file.create(tx, namespace.path, "a/f", size=8)

    # move file from 'a/f' to 'a/B/F.TXT'
    await crud.file.move(tx, namespace.path, "A/F", "A/b/F.TXT")

    assert not await crud.file.exists(tx, namespace.path, "a/f")

    f = await crud.file.get(tx, namespace.path, "a/b/f.txt")
    assert f.name == "F.TXT"
    assert f.path == "a/B/F.TXT"

    a, b = await crud.file.get_many(tx, namespace.path, ["a", "a/b"])
    assert a.size == 8
    assert b.size == 8


async def test_move_folder_is_case_insensitive(tx: DBTransaction, namespace: Namespace):
    await crud.file.create(tx, namespace.path, "a", mediatype=FOLDER)
    await crud.file.create(tx, namespace.path, "a/B", mediatype=FOLDER)
    await crud.file.create(tx, namespace.path, "a/B/f", size=8)
    await crud.file.create(tx, namespace.path, "a/c", mediatype=FOLDER)

    # move folder from 'a/B' to 'a/c/b'
    await crud.file.move(tx, namespace.path, "A/b", "A/C/b")

    assert not await crud.file.exists(tx, namespace.path, "a/b")

    a = await crud.file.get(tx, namespace.path, "a")
    assert a.size == 8

    b = await crud.file.get(tx, namespace.path, "a/c/b")
    assert b.name == "b"
    assert b.path == "a/c/b"

    c = await crud.file.get(tx, namespace.path, "a/c")
    assert c.size == 8

    f = await crud.file.get(tx, namespace.path, "a/c/b/f")
    assert f.path == "a/c/b/f"


async def test_move_but_next_path_is_already_taken(
    tx: DBTransaction,
    namespace: Namespace,
):
    await crud.file.create_folder(tx, namespace.path, "a/b")
    await crud.file.create_folder(tx, namespace.path, "a/c")

    with pytest.raises(errors.FileAlreadyExists):
        await crud.file.move(tx, namespace.path, "a/b", "a/c")

    with pytest.raises(errors.FileAlreadyExists):
        await crud.file.move(tx, namespace.path, "A/B", "A/C")


async def test_move_but_from_path_that_does_not_exists(
    tx: DBTransaction,
    namespace: Namespace,
):
    with pytest.raises(errors.FileNotFound):
        await crud.file.move(tx, namespace.path, "f", "a")


async def test_move_but_next_path_has_missing_parent(
    tx: DBTransaction,
    namespace: Namespace,
):
    await crud.file.create(tx, namespace.path, "f")

    with pytest.raises(errors.FileNotFound):
        await crud.file.move(tx, namespace.path, "f", "a/f")


async def test_move_but_next_path_is_not_a_folder(
    tx: DBTransaction,
    namespace: Namespace,
):
    await crud.file.create(tx, namespace.path, "a")
    await crud.file.create(tx, namespace.path, "f")

    with pytest.raises(errors.NotADirectory):
        await crud.file.move(tx, namespace.path, "a", "f/a")


@pytest.mark.parametrize(["name", "next_name"], [
    ("f.txt", "f (1).txt"),
    ("f.tar.gz", "f (1).tar.gz"),
    ("f (1).tar.gz", "f (1) (1).tar.gz"),
])
async def test_next_path(tx: DBTransaction, namespace: Namespace, name, next_name):
    await crud.file.create_folder(tx, namespace.path, "a/b")
    await crud.file.create(tx, namespace.path, f"a/b/{name}")

    next_path = await crud.file.next_path(tx, namespace.path, f"a/b/{name}")
    assert next_path == f"a/b/{next_name}"
    assert not await crud.file.exists(tx, namespace.path, next_name)


async def test_next_path_is_sequential(tx: DBTransaction, namespace: Namespace):
    await crud.file.create(tx, namespace.path, "f.tar.gz")
    await crud.file.create(tx, namespace.path, "f (1).tar.gz")

    next_path = await crud.file.next_path(tx, namespace.path, "f.tar.gz")
    assert next_path == "f (2).tar.gz"
    assert not await crud.file.exists(tx, namespace.path, "f (2).tar.gz")


async def test_next_path_is_case_insensitive(tx: DBTransaction, namespace: Namespace):
    await crud.file.create(tx, namespace.path, "F.TAR.GZ")
    await crud.file.create(tx, namespace.path, "F (1).tar.gz")

    next_path = await crud.file.next_path(tx, namespace.path, "f.tar.gz")
    assert next_path == "f (2).tar.gz"
    assert not await crud.file.exists(tx, namespace.path, "f (2).tar.gz")


async def test_next_path_returns_path_as_is(tx: DBTransaction, namespace: Namespace):
    next_path = await crud.file.next_path(tx, namespace.path, "f.txt")
    assert next_path == "f.txt"


async def test_inc_size_batch(tx: DBTransaction, namespace: Namespace):
    await crud.file.create_folder(tx, namespace.path, "a/b")
    await crud.file.create_folder(tx, namespace.path, "a/c")

    await crud.file.inc_size_batch(tx, namespace.path, paths=["a", "a/c"], size=16)

    paths = ["a", "a/b", "a/c"]
    a, b, c = await crud.file.get_many(tx, namespace.path, paths=paths)
    assert a.size == 16
    assert b.size == 0
    assert c.size == 16


async def test_inc_size_batch_is_case_insensitive(
    tx: DBTransaction,
    namespace: Namespace,
):
    await crud.file.create_folder(tx, namespace.path, "a/b")
    await crud.file.create_folder(tx, namespace.path, "a/C")

    await crud.file.inc_size_batch(tx, namespace.path, paths=["A", "A/c"], size=16)

    paths = ["a", "a/b", "a/c"]
    a, b, c = await crud.file.get_many(tx, namespace.path, paths=paths)
    assert a.size == 16
    assert b.size == 0
    assert c.size == 16


async def test_inc_size_batch_but_size_is_zero():
    # pass dummy DBTransaction, to check that method exists earlier with empty files
    result = await crud.file.inc_size_batch(
        object(),  # type: ignore
        "namespace",
        paths=["a/b"],
        size=0,
    )
    assert result is None


async def test_reset(tx, namespace: Namespace):
    await crud.file.create_folder(tx, namespace.path, "a")
    paths = ["x.txt", "a/f.txt", "Trash/f.txt"]
    for path in paths:
        await crud.file.create(tx, namespace.path, path)

    await crud.file.reset(tx, namespace.path)

    assert not await crud.file.exists(tx, namespace.path, "a")
    for path in paths:
        assert not await crud.file.exists(tx, namespace.path, path)

    assert not await crud.file.exists(tx, namespace.path, "Trash")
    assert await crud.file.exists(tx, namespace.path, ".")
