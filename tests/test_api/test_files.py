from __future__ import annotations

import secrets
from io import BytesIO
from typing import TYPE_CHECKING

import pytest
from cashews import cache

from app import config
from app.api.files.exceptions import (
    DownloadNotFound,
    FileAlreadyDeleted,
    FileAlreadyExists,
    IsADirectory,
    MalformedPath,
    NotADirectory,
    PathNotFound,
    ThumbnailUnavailable,
)

if TYPE_CHECKING:
    from app.entities import User
    from tests.conftest import TestClient

pytestmark = [pytest.mark.asyncio]


@pytest.mark.parametrize(["path", "name", "expected_path", "hidden"], [
    ("Folder", "Folder", None, False),
    ("Nested/Path/Folder", "Folder", None, False),
    (".Hidden Folder", ".Hidden Folder", None, True),
    (" Whitespaces ", "Whitespaces", "Whitespaces", False),
])
async def test_create_folder(
    client: TestClient, user: User, path, name, expected_path, hidden,
):
    payload = {"path": path}
    response = await client.login(user.id).post("/files/create_folder", json=payload)
    assert response.json()["name"] == name
    assert response.json()["path"] == (expected_path or path)
    assert response.json()["hidden"] is hidden
    assert response.status_code == 200


async def test_create_folder_but_folder_exists(client: TestClient, user: User):
    payload = {"path": "Trash"}
    response = await client.login(user.id).post("/files/create_folder", json=payload)
    assert response.json() == FileAlreadyExists(path='Trash').as_dict()
    assert response.status_code == 400


async def test_create_folder_but_parent_is_a_file(
    client: TestClient, user: User, file_factory
):
    await file_factory(user.id, path="file")
    payload = {"path": "file/folder"}
    response = await client.login(user.id).post("/files/create_folder", json=payload)
    assert response.json() == NotADirectory(path="file/folder").as_dict()
    assert response.status_code == 400


async def test_delete_immediately(client: TestClient, user: User):
    name = path = "Test Folder"
    payload = {"path": path}
    client.login(user.id)
    await client.post("/files/create_folder", json=payload)
    response = await client.post("/files/delete_immediately", json=payload)
    assert response.json()["name"] == name
    assert response.json()["path"] == path
    assert response.status_code == 200


async def test_delete_immediately_but_path_not_found(client: TestClient, user: User):
    data = {"path": "Test Folder"}
    response = await client.login(user.id).post("/files/delete_immediately", json=data)
    assert response.json() == PathNotFound(path="Test Folder").as_dict()
    assert response.status_code == 404


@pytest.mark.parametrize("path", [".", "Trash"])
async def test_delete_immediately_but_it_is_a_special_folder(
    client: TestClient, user: User, path: str,
):
    data = {"path": path}
    response = await client.login(user.id).post("/files/delete_immediately", json=data)
    message = f"Path '{path}' is a special path and can't be deleted"
    assert response.json() == MalformedPath(message).as_dict()
    assert response.status_code == 400


@pytest.mark.parametrize("path", ["f.txt", "ф.txt"])
async def test_download_file(client: TestClient, user: User, file_factory, path):
    content = b"Hello, World!"
    file = await file_factory(user.id, path=path, content=content)
    key = secrets.token_urlsafe()
    await cache.set(key, f"{user.namespace.path}:{file.path}")
    response = await client.login(user.id).get(f"/files/download?key={key}")
    assert response.status_code == 200
    assert response.headers["Content-Length"] == str(len(content))
    assert response.headers["Content-Type"] == "text/plain"
    assert response.content == content


async def test_download_folder(client: TestClient, user: User, file_factory):
    await file_factory(user.id, path="a/b/c/d.txt")
    key = secrets.token_urlsafe()
    await cache.set(key, f"{user.namespace.path}:a")
    response = await client.login(user.id).get(f"/files/download?key={key}")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "attachment/zip"
    assert response.content


async def test_download_but_key_is_invalid(client: TestClient):
    key = secrets.token_urlsafe()
    response = await client.get(f"/files/download?key={key}")
    assert response.status_code == 404
    assert response.json() == DownloadNotFound().as_dict()


async def test_download_but_file_not_found(client: TestClient, user: User):
    key = secrets.token_urlsafe()
    await cache.set(key, f"{user.namespace.path}:f.txt")
    response = await client.login(user.id).get(f"/files/download?key={key}")
    assert response.json() == PathNotFound(path="f.txt").as_dict()
    assert response.status_code == 404


# Use lambda to prevent long names in pytest output
@pytest.mark.parametrize("content_factory", [
    lambda: b"Hello, World!",
    lambda: b"1" * config.APP_MAX_DOWNLOAD_WITHOUT_STREAMING + b"1",
])
async def test_download_file_with_post(
    client: TestClient, user: User, file_factory, content_factory,
):
    content = content_factory()
    file = await file_factory(user.id, content=content)
    payload = {"path": file.path}
    response = await client.login(user.id).post("/files/download", json=payload)
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "text/plain"
    assert response.headers["Content-Length"] == str(len(content))
    assert response.content == content


async def test_download_file_with_non_latin_name_with_post(
    client: TestClient, user: User, file_factory
):
    file = await file_factory(user.id, path="файл.txt")
    payload = {"path": file.path}
    response = await client.login(user.id).post("/files/download", json=payload)
    assert response.status_code == 200


async def test_download_folder_with_post(client: TestClient, user: User, file_factory):
    await file_factory(user.id, path="a/b/c/d.txt")
    payload = {"path": "a"}
    response = await client.login(user.id).post("/files/download", json=payload)
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "attachment/zip"
    assert "Content-Length" not in response.headers
    assert response.content


async def test_download_with_post_but_file_not_found(client: TestClient, user: User):
    payload = {"path": "f.txt"}
    response = await client.login(user.id).post("/files/download", json=payload)
    assert response.json() == PathNotFound(path="f.txt").as_dict()
    assert response.status_code == 404


async def test_empty_trash(client: TestClient, user: User):
    response = await client.login(user.id).post("/files/empty_trash")
    assert response.status_code == 200
    assert response.json()["path"] == "Trash"


async def test_get_download_url(client: TestClient, user: User, file_factory):
    file = await file_factory(user.id)
    payload = {"path": file.path}
    response = await client.login(user.id).post("/files/get_download_url", json=payload)
    download_url = response.json()["download_url"]
    assert download_url.startswith(str(client.base_url))
    assert response.status_code == 200
    key = download_url[download_url.index("=") + 1:]
    value = await cache.get(key)
    assert value == f"{user.namespace.path}:{file.path}"


async def test_get_download_url_but_file_not_found(client: TestClient, user: User):
    payload = {"path": "wrong/path"}
    response = await client.login(user.id).post("/files/get_download_url", json=payload)
    assert response.json() == PathNotFound(path="wrong/path").as_dict()
    assert response.status_code == 404


@pytest.mark.parametrize("name", ["im.jpeg", "изо.jpeg"])
async def test_get_thumbnail(client: TestClient, user: User, image_factory, name):
    file = await image_factory(user.id, path=name)
    payload = {"path": file.path}
    client.login(user.id)
    response = await client.post("/files/get_thumbnail?size=xs", json=payload)
    assert response.headers["Content-Disposition"] == f'inline; filename="{file.name}"'
    assert int(response.headers["Content-Length"]) < file.size
    assert response.headers["Content-Type"] == "image/jpeg"
    assert response.content


async def test_get_thumbnail_but_path_not_found(client: TestClient, user: User):
    client.login(user.id)
    payload = {"path": "im.jpeg"}
    response = await client.post("/files/get_thumbnail?size=sm", json=payload)
    assert response.json() == PathNotFound(path="im.jpeg").as_dict()


async def test_get_thumbnail_but_path_is_a_folder(client: TestClient, user: User):
    client.login(user.id)
    payload = {"path": "."}
    response = await client.post("/files/get_thumbnail?size=sm", json=payload)
    assert response.json() == IsADirectory(path=".").as_dict()


async def test_get_thumbnail_but_file_is_not_thumbnailable(
    client: TestClient, user: User, file_factory,
):
    file = await file_factory(user.id)
    client.login(user.id)
    payload = {"path": file.path}
    response = await client.post("/files/get_thumbnail?size=sm", json=payload)
    assert response.json() == ThumbnailUnavailable(path=file.path).as_dict()


async def test_list_folder(client: TestClient, user: User, file_factory):
    await file_factory(user.id, path="file.txt")
    await file_factory(user.id, path="folder/file.txt")
    payload = {"path": "."}
    response = await client.login(user.id).post("/files/list_folder", json=payload)
    assert response.status_code == 200
    assert response.json()["path"] == "."
    assert response.json()["count"] == 2
    assert response.json()["items"][0]["name"] == "folder"
    assert response.json()["items"][1]["name"] == "file.txt"


async def test_list_folder_but_path_does_not_exists(client: TestClient, user: User):
    payload = {"path": "wrong/path"}
    response = await client.login(user.id).post("/files/list_folder", json=payload)
    assert response.status_code == 404
    assert response.json() == PathNotFound(path="wrong/path").as_dict()


async def test_list_folder_but_path_is_not_a_folder(
    client: TestClient, user: User, file_factory,
):
    file = await file_factory(user.id, path="f.txt")
    payload = {"path": file.path}
    response = await client.login(user.id).post("/files/list_folder", json=payload)
    assert response.json() == NotADirectory(path="f.txt").as_dict()


async def test_move(client: TestClient, user: User, file_factory):
    await file_factory(user.id, path="file.txt")
    payload = {"from_path": "file.txt", "to_path": ".file.txt"}
    response = await client.login(user.id).post("/files/move", json=payload)
    assert response.status_code == 200
    assert response.json()["name"] == ".file.txt"
    assert response.json()["path"] == ".file.txt"


@pytest.mark.parametrize("path", [".", "Trash"])
async def test_move_but_it_is_a_special_path(client: TestClient, user: User, path):
    payload = {"from_path": path, "to_path": "Trashbin"}
    response = await client.login(user.id).post("/files/move", json=payload)
    message = "Can't move Home or Trash folder"
    assert response.json() == MalformedPath(message).as_dict()
    assert response.status_code == 400


@pytest.mark.parametrize("next_path", [".", "Trash"])
async def test_move_but_to_a_special_path(
    client: TestClient, user: User, file_factory, next_path,
):
    file = await file_factory(user.id)
    payload = {"from_path": file.path, "to_path": next_path}
    response = await client.login(user.id).post("/files/move", json=payload)
    message = "Can't move Home or Trash folder"
    assert response.json() == MalformedPath(message).as_dict()
    assert response.status_code == 400


async def test_move_but_path_is_recursive(client: TestClient, user: User):
    payload = {"from_path": "a/b", "to_path": "a/b/c"}
    response = await client.login(user.id).post("/files/move", json=payload)
    message = "Destination path should not start with source path"
    assert response.json() == MalformedPath(message).as_dict()
    assert response.status_code == 400


async def test_move_but_file_exists(client: TestClient, user: User, file_factory):
    file_a = await file_factory(user.id, path="folder/file.txt")
    file_b = await file_factory(user.id, path="file.txt")
    payload = {"from_path": file_a.path, "to_path": file_b.path}
    response = await client.login(user.id).post("/files/move", json=payload)
    assert response.status_code == 400
    assert response.json() == FileAlreadyExists(path=file_b.path).as_dict()


async def test_move_but_file_not_found(client: TestClient, user: User):
    payload = {"from_path": "file_a.txt", "to_path": "file_b.txt"}
    response = await client.login(user.id).post("/files/move", json=payload)
    assert response.status_code == 404
    assert response.json() == PathNotFound(path="file_a.txt").as_dict()


async def test_move_but_to_path_is_a_file(client: TestClient, user: User, file_factory):
    file_a = await file_factory(user.id, path="file_a.txt")
    file_b = await file_factory(user.id, path="file_b.txt")
    payload = {"from_path": file_a.path, "to_path": f"{file_b.path}/{file_a.path}"}
    response = await client.login(user.id).post("/files/move", json=payload)
    assert response.status_code == 400
    assert response.json() == NotADirectory(path=payload["to_path"]).as_dict()


async def test_move_but_path_missing_parent(
    client: TestClient, user: User, file_factory
):
    file_a = await file_factory(user.id, path="file_a.txt")
    payload = {"from_path": file_a.path, "to_path": f"folder/{file_a.path}"}
    response = await client.login(user.id).post("/files/move", json=payload)
    message = "Some parents don't exist in the destination path"
    assert response.json() == MalformedPath(message).as_dict()
    assert response.status_code == 400


@pytest.mark.parametrize(["file_path", "path", "expected_path"], [
    ("file.txt", "file.txt", "Trash/file.txt"),  # move file to the Trash
    ("a/b/c/d.txt", "a/b", "Trash/b"),  # move folder to the Trash
])
async def test_move_to_trash(
    client: TestClient, user: User, file_factory, file_path, path, expected_path,
):
    await file_factory(user.id, path=file_path)
    payload = {"path": path}
    response = await client.login(user.id).post("/files/move_to_trash", json=payload)
    assert response.status_code == 200
    assert response.json()["path"] == expected_path


async def test_move_to_trash_but_it_is_a_trash(client: TestClient, user: User):
    payload = {"path": "Trash"}
    response = await client.login(user.id).post("/files/move_to_trash", json=payload)
    message = "Can't move Trash into itself"
    assert response.json() == MalformedPath(message).as_dict()
    assert response.status_code == 400


async def test_move_to_trash_but_file_is_in_trash(
    client: TestClient, user: User, file_factory,
):
    file = await file_factory(user.id, path="Trash/file.txt")
    payload = {"path": file.path}
    response = await client.login(user.id).post("/files/move_to_trash", json=payload)
    assert response.status_code == 400
    assert response.json() == FileAlreadyDeleted(path=file.path).as_dict()


async def test_move_to_trash_but_file_not_found(client: TestClient, user: User):
    payload = {"path": "file.txt"}
    response = await client.login(user.id).post("/files/move_to_trash", json=payload)
    assert response.status_code == 404
    assert response.json() == PathNotFound(path=payload["path"]).as_dict()


async def test_upload(client: TestClient, user: User):
    payload = {
        "file": BytesIO(b"Dummy file"),
        "path": (None, "folder/file.txt"),
    }
    client.login(user.id)
    response = await client.post("/files/upload", files=payload)  # type: ignore
    assert response.status_code == 200
    assert response.json()["file"]["path"] == "folder/file.txt"
    assert len(response.json()["updates"]) == 2


async def test_upload_but_to_a_special_path(client: TestClient, user: User):
    payload = {
        "file": BytesIO(b"Dummy file"),
        "path": (None, "Trash"),
    }
    client.login(user.id)
    response = await client.post("/files/upload", files=payload)  # type: ignore
    message = "Uploads to the Trash are not allowed"
    assert response.json() == MalformedPath(message).as_dict()
    assert response.status_code == 400


async def test_upload_but_path_is_a_file(client: TestClient, user: User, file_factory):
    file = await file_factory(user.id, path="f.txt")
    payload = {
        "file": BytesIO(b"Dummy file"),
        "path": (None, f"{file.path}/dummy"),
    }
    client.login(user.id)
    response = await client.post("/files/upload", files=payload)  # type: ignore
    assert response.json() == NotADirectory(path=f"{file.path}/dummy").as_dict()
    assert response.status_code == 400
