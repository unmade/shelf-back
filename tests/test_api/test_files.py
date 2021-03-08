from __future__ import annotations

import secrets
from io import BytesIO
from typing import TYPE_CHECKING

import pytest
from cashews import cache

from app import config
from app.api.files.exceptions import (
    AlreadyDeleted,
    AlreadyExists,
    DownloadNotFound,
    InvalidPath,
    PathNotFound,
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
    assert response.status_code == 200
    assert response.json()["name"] == name
    assert response.json()["path"] == (expected_path or path)
    assert response.json()["hidden"] is hidden


async def test_create_folder_but_folder_exists(client: TestClient, user: User):
    payload = {"path": "Trash"}
    response = await client.login(user.id).post("/files/create_folder", json=payload)
    assert response.status_code == 400
    assert response.json() == AlreadyExists().as_dict()


async def test_create_folder_but_parent_is_a_file(
    client: TestClient, user: User, file_factory
):
    await file_factory(user.id, path="file")
    payload = {"path": "file/folder"}
    response = await client.login(user.id).post("/files/create_folder", json=payload)
    assert response.status_code == 400
    assert response.json() == InvalidPath().as_dict()


async def test_delete_immediately(client: TestClient, user: User):
    name = path = "Test Folder"
    payload = {"path": path}
    client.login(user.id)
    await client.post("/files/create_folder", json=payload)
    response = await client.post("/files/delete_immediately", json=payload)
    assert response.status_code == 200
    assert response.json()["name"] == name
    assert response.json()["path"] == path


async def test_delete_immediately_but_path_not_found(client: TestClient, user: User):
    data = {"path": "Test Folder"}
    response = await client.login(user.id).post("/files/delete_immediately", json=data)
    assert response.status_code == 404
    assert response.json() == PathNotFound().as_dict()


@pytest.mark.parametrize("path", [".", "Trash"])
async def test_delete_immediately_but_it_is_a_special_folder(
    client: TestClient, user: User, path: str,
):
    data = {"path": path}
    response = await client.login(user.id).post("/files/delete_immediately", json=data)
    assert response.status_code == 400
    assert response.json() == InvalidPath().as_dict()


async def test_download_file(client: TestClient, user: User, file_factory):
    file = await file_factory(user.id)
    key = secrets.token_urlsafe()
    await cache.set(key, f"{user.username}/{file.path}")
    response = await client.login(user.id).get(f"/files/download?key={key}")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "attachment/zip"
    assert response.content


async def test_download_folder(client: TestClient, user: User, file_factory):
    await file_factory(user.id, path="a/b/c/d.txt")
    key = secrets.token_urlsafe()
    await cache.set(key, f"{user.username}/a")
    response = await client.login(user.id).get(f"/files/download?key={key}")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "attachment/zip"
    assert response.content


async def test_download_but_key_is_invalid(client: TestClient):
    key = secrets.token_urlsafe()
    response = await client.get(f"/files/download?key={key}")
    assert response.status_code == 404
    assert response.json() == DownloadNotFound().as_dict()


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
    assert response.json() == PathNotFound().as_dict()
    assert response.status_code == 404


async def test_empty_trash(client: TestClient, user: User):
    response = await client.login(user.id).post("/files/empty_trash")
    assert response.status_code == 200
    assert response.json()["path"] == "Trash"


async def test_get_download_url(client: TestClient, user: User, file_factory):
    file = await file_factory(user.id)
    payload = {"path": file.path}
    response = await client.login(user.id).post("/files/get_download_url", json=payload)
    assert response.status_code == 200
    assert response.json()["download_url"].startswith(str(client.base_url))


async def test_get_download_url_but_file_not_found(client: TestClient, user: User):
    payload = {"path": "wrong/path"}
    response = await client.login(user.id).post("/files/get_download_url", json=payload)
    assert response.json() == PathNotFound().as_dict()
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
    assert response.json() == PathNotFound().as_dict()


async def test_get_thumbnail_but_path_is_a_folder(client: TestClient, user: User):
    client.login(user.id)
    payload = {"path": "."}
    response = await client.post("/files/get_thumbnail?size=sm", json=payload)
    assert response.json() == InvalidPath().as_dict()


async def test_get_thumbnail_but_file_is_not_thumbnailable(
    client: TestClient, user: User, file_factory,
):
    file = await file_factory(user.id)
    client.login(user.id)
    payload = {"path": file.path}
    response = await client.post("/files/get_thumbnail?size=sm", json=payload)
    assert response.json() == InvalidPath().as_dict()


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
    assert response.json() == PathNotFound().as_dict()


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
    assert response.status_code == 400
    message = "should not be Home or Trash folder."
    assert response.json() == InvalidPath(message).as_dict()


@pytest.mark.parametrize("next_path", [".", "Trash"])
async def test_move_but_to_a_special_path(
    client: TestClient, user: User, file_factory, next_path,
):
    file = await file_factory(user.id)
    payload = {"from_path": file.path, "to_path": next_path}
    response = await client.login(user.id).post("/files/move", json=payload)
    assert response.status_code == 400
    message = "should not be Home or Trash folder."
    assert response.json() == InvalidPath(message).as_dict()


async def test_move_but_path_is_recursive(client: TestClient, user: User):
    payload = {"from_path": "a/b", "to_path": "a/b/c"}
    response = await client.login(user.id).post("/files/move", json=payload)
    assert response.status_code == 400
    message = "destination path should not starts with source path."
    assert response.json() == InvalidPath(message).as_dict()


async def test_move_but_file_not_found(client: TestClient, user: User):
    payload = {"from_path": "file_a.txt", "to_path": "file_b.txt"}
    response = await client.login(user.id).post("/files/move", json=payload)
    assert response.status_code == 404
    assert response.json() == PathNotFound().as_dict()


async def test_move_but_file_exists(client: TestClient, user: User, file_factory):
    file_a = await file_factory(user.id, path="folder/file.txt")
    file_b = await file_factory(user.id, path="file.txt")
    payload = {"from_path": file_a.path, "to_path": file_b.path}
    response = await client.login(user.id).post("/files/move", json=payload)
    assert response.status_code == 400
    assert response.json() == AlreadyExists().as_dict()


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
    assert response.status_code == 400
    assert response.json() == InvalidPath().as_dict()


async def test_move_to_trash_but_file_is_in_trash(
    client: TestClient, user: User, file_factory,
):
    file = await file_factory(user.id, path="Trash/file.txt")
    payload = {"path": file.path}
    response = await client.login(user.id).post("/files/move_to_trash", json=payload)
    assert response.status_code == 400
    assert response.json() == AlreadyDeleted().as_dict()


async def test_move_to_trash_but_file_not_found(client: TestClient, user: User):
    payload = {"path": "file.txt"}
    response = await client.login(user.id).post("/files/move_to_trash", json=payload)
    assert response.status_code == 404
    assert response.json() == PathNotFound().as_dict()


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
    assert response.status_code == 400
    assert response.json() == InvalidPath().as_dict()
