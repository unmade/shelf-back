from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from app import crud, errors, taskgroups
from app.mediatypes import FOLDER, OCTET_STREAM

if TYPE_CHECKING:
    from app.entities import Namespace
    from app.typedefs import DBClient, DBTransaction
    from tests.factories import FileFactory, NamespaceFactory

pytestmark = [pytest.mark.asyncio, pytest.mark.database]


async def test_create(tx: DBTransaction, namespace: Namespace):
    path = Path("a/b/f")
    for parent in reversed(path.parents[:-1]):
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

    await taskgroups.gather(*(
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
    assert {f.id for f in files} == set(ids)


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
    assert {f.id for f in files} == {f.id for f in files_a}


async def test_get_many(tx: DBTransaction, namespace: Namespace):
    await crud.file.create(tx, namespace.path, "a", mediatype=FOLDER)
    await crud.file.create(tx, namespace.path, "a/b", mediatype=FOLDER)
    await crud.file.create(tx, namespace.path, "a/c", mediatype=FOLDER)
    await crud.file.create(tx, namespace.path, "a/f")

    paths = ["a", "a/c", "a/f", "a/d"]
    files = await crud.file.get_many(tx, namespace.path, paths=paths)

    assert len(files) == 3
    for file, path in zip(files, paths[:-1], strict=True):
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
