from __future__ import annotations

import secrets
import urllib.parse
import uuid
from io import BytesIO
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app import config, errors, tasks
from app.api import shortcuts
from app.api.files.exceptions import (
    DownloadNotFound,
    FileAlreadyDeleted,
    FileAlreadyExists,
    MalformedPath,
    NotADirectory,
    PathNotFound,
    StorageQuotaExceeded,
    UploadFileTooLarge,
)
from app.domain.entities import Folder
from app.entities import Exif, RelocationPath

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from fastapi import FastAPI

    from app.entities import FileTaskResult, Namespace
    from tests.conftest import TestClient
    from tests.factories import (
        AccountFactory,
        FileFactory,
        FileMetadataFactory,
        FingerprintFactory,
    )

pytestmark = [pytest.mark.asyncio, pytest.mark.database(transaction=True)]


class TestCreateFolder:
    @pytest.fixture
    def ns_service(self, app: FastAPI):
        service = app.state.provider.service
        ns_service_mock = mock.MagicMock(service.namespace)
        with mock.patch.object(service, "namespace", ns_service_mock) as mocked:
            yield mocked

    @pytest.mark.parametrize(["path", "expected_path"], [
        ("Folder", "Folder"),
        ("Nested/Path/Folder", "Nested/Path/Folder",),
        (".Hidden Folder", ".Hidden Folder",),
        (" Whitespaces ", "Whitespaces",),
    ])
    async def test(
        self,
        client: TestClient,
        namespace: Namespace,
        ns_service: MagicMock,
        path: str,
        expected_path: str,
    ):
        ns_service.create_folder.return_value = Folder(
            id=uuid.uuid4(),
            ns_path=str(namespace.path),
            name=expected_path.split('/')[-1],
            path=expected_path,
        )
        payload = {"path": path}
        client.login(namespace.owner.id)
        response = await client.post("/files/create_folder", json=payload)
        assert response.status_code == 200
        ns_service.create_folder.assert_awaited_once_with(
            namespace.path, expected_path
        )

    async def test_when_folder_exists(
        self, client: TestClient, namespace: Namespace, ns_service: MagicMock
    ):
        ns_service.create_folder.side_effect = errors.FileAlreadyExists
        payload = {"path": "Trash"}
        client.login(namespace.owner.id)
        response = await client.post("/files/create_folder", json=payload)
        assert response.json() == FileAlreadyExists(path='Trash').as_dict()
        assert response.status_code == 400
        ns_service.create_folder.assert_awaited_once_with(namespace.path, "Trash")

    async def test_when_parent_is_a_file(
        self, client: TestClient, namespace: Namespace, ns_service: MagicMock
    ):
        ns_service.create_folder.side_effect = errors.NotADirectory()
        path = "file/folder"
        payload = {"path": path}
        client.login(namespace.owner.id)
        response = await client.post("/files/create_folder", json=payload)
        assert response.json() == NotADirectory(path="file/folder").as_dict()
        assert response.status_code == 400
        ns_service.create_folder.assert_awaited_once_with(namespace.path, path)


@pytest.mark.parametrize(["path", "name", "expected_path", "hidden"], [
    ("Folder", "Folder", None, False),
    ("Nested/Path/Folder", "Folder", None, False),
    (".Hidden Folder", ".Hidden Folder", None, True),
    (" Whitespaces ", "Whitespaces", "Whitespaces", False),
])
async def test_create_folder(
    client: TestClient,
    namespace: Namespace,
    path: str,
    name: str,
    expected_path: str | None,
    hidden: bool,
):
    payload = {"path": path}
    client.login(namespace.owner.id)
    response = await client.post("/files/create_folder", json=payload)
    assert response.json()["name"] == name
    assert response.json()["path"] == (expected_path or path)
    assert response.json()["hidden"] is hidden
    assert response.status_code == 200


@pytest.mark.usefixtures("celery_session_worker")
async def test_delete_immediately_batch(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    files = [await file_factory(namespace.path) for _ in range(3)]
    payload = {
        "items": [
            {"path": file.path} for file in files
        ],
    }
    client.login(namespace.owner.id)
    await client.post("/files/create_folder", json=payload)
    response = await client.post("/files/delete_immediately_batch", json=payload)
    assert "async_task_id" in response.json()
    assert response.status_code == 200

    task_id = response.json()["async_task_id"]
    task = tasks.celery_app.AsyncResult(task_id)
    result: list[FileTaskResult] = task.get(timeout=2)
    assert len(result) == 3
    for idx, file in enumerate(files):
        deleted_file = result[idx].file
        assert deleted_file is not None
        assert deleted_file.id == file.id
        assert result[idx].err_code is None


@pytest.mark.usefixtures("celery_session_worker")
@pytest.mark.parametrize("path", [".", "Trash"])
async def test_delete_immediately_batch_but_it_is_a_special_folder(
    client: TestClient,
    namespace: Namespace,
    path: str,
):
    payload = {"items": [{"path": path}]}
    client.login(namespace.owner.id)
    response = await client.post("/files/delete_immediately_batch", json=payload)
    message = f"Path '{path}' is a special path and can't be deleted"
    assert response.json() == MalformedPath(message).as_dict()
    assert response.status_code == 400


@pytest.mark.usefixtures("celery_session_worker")
async def test_delete_immediately_batch_check_task_is_pending(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path, path="folder/a.txt")
    task = tasks.delete_immediately_batch.delay(namespace, [file.path])

    payload = {"async_task_id": task.id}
    client.login(namespace.owner.id)
    response = await client.post("/files/delete_immediately_batch/check", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == 'pending'
    assert response.json()["result"] is None

    # sometimes there is a race condition between task and test teardown,
    # so ensure task is completed
    task.get(timeout=2)


@pytest.mark.usefixtures("celery_session_worker")
async def test_delete_immediately_batch_check_task_is_completed(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path, path="folder/a.txt")
    task = tasks.delete_immediately_batch.delay(namespace, [file.path])
    task.get(timeout=1)

    payload = {"async_task_id": task.id}
    client.login(namespace.owner.id)
    response = await client.post("/files/delete_immediately_batch/check", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "completed"

    result = response.json()["result"]

    assert result[0]["file"]["id"] == str(file.id)
    assert result[0]["err_code"] is None


@pytest.mark.parametrize("path", ["f.txt", "ф.txt"])
async def test_download_file(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
    path: str,
):
    content = b"Hello, World!"
    file = await file_factory(namespace.path, path=path, content=content)
    key = await shortcuts.create_download_cache(namespace.path, file.path)
    client.login(namespace.owner.id)
    response = await client.get(f"/files/download?key={key}")
    assert response.status_code == 200
    assert response.headers["Content-Length"] == str(len(content))
    assert response.headers["Content-Type"] == "text/plain"
    assert response.content == content


async def test_download_folder(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    await file_factory(namespace.path, path="a/b/c/d.txt")
    key = await shortcuts.create_download_cache(namespace.path, "a")
    client.login(namespace.owner.id)
    response = await client.get(f"/files/download?key={key}")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "attachment/zip"
    assert response.content


async def test_download_but_key_is_invalid(client: TestClient):
    key = secrets.token_urlsafe()
    response = await client.get(f"/files/download?key={key}")
    assert response.status_code == 404
    assert response.json() == DownloadNotFound().as_dict()


async def test_download_but_file_not_found(client: TestClient, namespace: Namespace):
    key = await shortcuts.create_download_cache(namespace.path, "f.txt")
    client.login(namespace.owner.id)
    response = await client.get(f"/files/download?key={key}")
    assert response.json() == PathNotFound(path="f.txt").as_dict()
    assert response.status_code == 404


# Use lambda to prevent long names in pytest output
@pytest.mark.parametrize("content_factory", [
    lambda: b"Hello, World!",
    lambda: b"1" * config.APP_MAX_DOWNLOAD_WITHOUT_STREAMING + b"1",
])
async def test_download_file_with_post(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
    content_factory,
):
    content = content_factory()
    file = await file_factory(namespace.path, content=content)
    payload = {"path": file.path}
    client.login(namespace.owner.id)
    response = await client.post("/files/download", json=payload)
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "text/plain"
    assert response.headers["Content-Length"] == str(len(content))
    assert response.content == content


async def test_download_file_with_non_latin_name_with_post(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path, path="файл.txt")
    payload = {"path": file.path}
    client.login(namespace.owner.id)
    response = await client.post("/files/download", json=payload)
    assert response.status_code == 200


async def test_download_folder_with_post(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    await file_factory(namespace.path, path="a/b/c/d.txt")
    payload = {"path": "a"}
    client.login(namespace.owner.id)
    response = await client.post("/files/download", json=payload)
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "attachment/zip"
    assert "Content-Length" not in response.headers
    assert response.content


async def test_download_with_post_but_file_not_found(
    client: TestClient,
    namespace: Namespace,
):
    payload = {"path": "f.txt"}
    client.login(namespace.owner.id)
    response = await client.post("/files/download", json=payload)
    assert response.json() == PathNotFound(path="f.txt").as_dict()
    assert response.status_code == 404


@pytest.mark.usefixtures("celery_session_worker")
async def test_empty_trash(client: TestClient, namespace: Namespace):
    client.login(namespace.owner.id)
    response = await client.post("/files/empty_trash")
    assert "async_task_id" in response.json()
    assert response.status_code == 200

    task_id = response.json()["async_task_id"]
    task = tasks.celery_app.AsyncResult(task_id)
    result: None = task.get(timeout=2)
    assert result is None


@pytest.mark.usefixtures("celery_session_worker")
async def test_empty_trash_check_task_is_pending(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    await file_factory(namespace.path, path="Trash/a.txt")
    await file_factory(namespace.path, path="Trash/folder/b.txt")
    task = tasks.empty_trash.delay(namespace)
    payload = {"async_task_id": task.id}

    client.login(namespace.owner.id)
    response = await client.post("/files/empty_trash/check", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == 'pending'
    assert response.json()["result"] is None

    # sometimes there is a race condition between task and test teardown,
    # so ensure task is completed
    task.get(timeout=2)


@pytest.mark.usefixtures("celery_session_worker")
async def test_empty_trash_check_task_is_completed(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    await file_factory(namespace.path, path="Trash/a.txt")
    await file_factory(namespace.path, path="Trash/folder/b.txt")
    task = tasks.empty_trash.delay(namespace)
    task.get(timeout=1)

    payload = {"async_task_id": task.id}
    client.login(namespace.owner.id)
    response = await client.post("/files/empty_trash/check", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["result"] is None


async def test_find_duplicates(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
    fingerprint_factory: FingerprintFactory,
):
    ns_path = namespace.path

    file_1 = await file_factory(ns_path, "f1.txt")
    file_1_match = await file_factory(ns_path, "f1 (match).txt")

    await fingerprint_factory(file_1.id, 56797, 56781, 18381, 58597)
    await fingerprint_factory(file_1_match.id, 56797, 56797, 18381, 58597)

    payload = {"path": "."}
    client.login(namespace.owner.id)
    response = await client.post("/files/find_duplicates", json=payload)
    assert response.json()["path"] == "."
    assert response.json()["count"] == 1
    assert len(response.json()["items"]) == 1
    assert len(response.json()["items"][0]) == 2
    names = {
        response.json()["items"][0][0]["name"],
        response.json()["items"][0][1]["name"],
    }
    assert names == {"f1.txt", "f1 (match).txt"}
    assert response.status_code == 200


async def test_find_duplicates_with_zero_distance(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
    fingerprint_factory: FingerprintFactory,
):
    ns_path = namespace.path

    file_1 = await file_factory(ns_path, "f1.txt")
    file_1_match = await file_factory(ns_path, "f1 (match).txt")

    await fingerprint_factory(file_1.id, 56797, 56781, 18381, 58597)
    await fingerprint_factory(file_1_match.id, 56797, 56797, 18381, 58597)

    payload = {"path": ".", "max_distance": 0}
    client.login(namespace.owner.id)
    response = await client.post("/files/find_duplicates", json=payload)
    assert response.json()["path"] == "."
    assert response.json()["count"] == 0
    assert len(response.json()["items"]) == 0


async def test_get_batch(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    files = [
        await file_factory(namespace.path, path=f"{i}.txt")
        for i in range(3)
    ]
    payload = {"ids": [file.id for file in files[::2]]}
    client.login(namespace.owner.id)
    response = await client.post("/files/get_batch", json=payload)
    assert response.json()["count"] == 2
    assert len(response.json()["items"]) == 2
    assert response.json()["items"][0]["id"] == files[0].id
    assert response.json()["items"][1]["id"] == files[2].id
    assert response.status_code == 200


async def test_get_download_url(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path)
    payload = {"path": file.path}
    client.login(namespace.owner.id)
    response = await client.post("/files/get_download_url", json=payload)
    download_url = response.json()["download_url"]
    assert download_url.startswith(str(client.base_url))
    assert response.status_code == 200
    parts = urllib.parse.urlsplit(download_url)
    qs = urllib.parse.parse_qs(parts.query)
    assert len(qs["key"]) == 1


async def test_get_download_url_but_file_not_found(
    client: TestClient,
    namespace: Namespace,
):
    payload = {"path": "wrong/path"}
    client.login(namespace.owner.id)
    response = await client.post("/files/get_download_url", json=payload)
    assert response.json() == PathNotFound(path="wrong/path").as_dict()
    assert response.status_code == 404


async def test_get_content_metadata(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
    file_metadata_factory: FileMetadataFactory,
):
    file = await file_factory(namespace.path, "img.jpg")
    exif = Exif(width=1280, height=800)
    await file_metadata_factory(file.id, data=exif)
    payload = {"path": file.path}
    client.login(namespace.owner.id)
    response = await client.post("/files/get_content_metadata", json=payload)
    assert response.json()["file_id"] == file.id
    assert response.json()["data"] == exif.dict()
    assert response.status_code == 200


async def test_get_content_metadata_on_a_file_with_no_meta(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path, "img.jpg")
    payload = {"path": file.path}
    client.login(namespace.owner.id)
    response = await client.post("/files/get_content_metadata", json=payload)
    assert response.json()["file_id"] == file.id
    assert response.json()["data"] is None
    assert response.status_code == 200


async def test_get_content_metadata_but_file_not_found(
    client: TestClient,
    namespace: Namespace,
):
    payload = {"path": "wrong/path"}
    client.login(namespace.owner.id)
    response = await client.post("/files/get_content_metadata", json=payload)
    assert response.json() == PathNotFound(path="wrong/path").as_dict()
    assert response.status_code == 404


@pytest.mark.parametrize("name", ["im.jpeg", "изо.jpeg"])
async def test_get_thumbnail(
    client: TestClient,
    namespace: Namespace,
    image_content: BytesIO,
    file_factory: FileFactory,
    name: str,
):
    file = await file_factory(namespace.path, path=name, content=image_content)
    mtime = file.mtime
    client.login(namespace.owner.id)
    response = await client.get(f"/files/get_thumbnail/{file.id}?size=xs&mtime={mtime}")
    assert response.content
    headers = response.headers
    assert headers["Content-Disposition"] == f'inline; filename="{file.name}"'
    assert int(headers["Content-Length"]) < file.size
    assert headers["Content-Type"] == "image/webp"
    assert headers["Cache-Control"] == "private, max-age=31536000, no-transform"


async def test_list_folder(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
    image_content: BytesIO,
):
    img = await file_factory(namespace.path, path="im.jpeg", content=image_content)
    thumbnail_url = f"{client.base_url}/files/get_thumbnail/{img.id}"
    await file_factory(namespace.path, path="file.txt")
    await file_factory(namespace.path, path="folder/file.txt")
    payload = {"path": "."}
    client.login(namespace.owner.id)
    response = await client.post("/files/list_folder", json=payload)
    assert response.status_code == 200
    assert response.json()["path"] == "."
    assert response.json()["count"] == 3
    assert response.json()["items"][0]["name"] == "folder"
    assert response.json()["items"][0]["thumbnail_url"] is None
    assert response.json()["items"][1]["name"] == "file.txt"
    assert response.json()["items"][1]["thumbnail_url"] is None
    assert response.json()["items"][2]["name"] == "im.jpeg"
    assert response.json()["items"][2]["thumbnail_url"] == thumbnail_url


async def test_list_folder_but_path_does_not_exists(
    client: TestClient,
    namespace: Namespace,
):
    payload = {"path": "wrong/path"}
    client.login(namespace.owner.id)
    response = await client.post("/files/list_folder", json=payload)
    assert response.status_code == 404
    assert response.json() == PathNotFound(path="wrong/path").as_dict()


async def test_list_folder_but_path_is_not_a_folder(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path, path="f.txt")
    payload = {"path": file.path}
    client.login(namespace.owner.id)
    response = await client.post("/files/list_folder", json=payload)
    assert response.json() == NotADirectory(path="f.txt").as_dict()


@pytest.mark.parametrize(["path", "next_path"], [
    ("file.txt", ".file.txt"),
    ("f", "f.txt"),
])
async def test_move(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
    path: str,
    next_path: str,
):
    await file_factory(namespace.path, path=path)
    payload = {"from_path": path, "to_path": next_path}
    client.login(namespace.owner.id)
    response = await client.post("/files/move", json=payload)
    assert response.status_code == 200
    assert response.json()["name"] == next_path
    assert response.json()["path"] == next_path


@pytest.mark.parametrize("path", [".", "Trash"])
async def test_move_but_it_is_a_special_path(
    client: TestClient,
    namespace: Namespace,
    path: str,
):
    payload = {"from_path": path, "to_path": "Trashbin"}
    client.login(namespace.owner.id)
    response = await client.post("/files/move", json=payload)
    message = "Can't move Home or Trash folder"
    assert response.json() == MalformedPath(message).as_dict()
    assert response.status_code == 400


@pytest.mark.parametrize("next_path", [".", "Trash"])
async def test_move_but_to_a_special_path(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
    next_path: str,
):
    file = await file_factory(namespace.path)
    payload = {"from_path": file.path, "to_path": next_path}
    client.login(namespace.owner.id)
    response = await client.post("/files/move", json=payload)
    message = "Can't move Home or Trash folder"
    assert response.json() == MalformedPath(message).as_dict()
    assert response.status_code == 400


async def test_move_but_it_is_inside_trash_folder(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path, path="Trash/f.txt")
    payload = {"from_path": file.path, "to_path": "Trash/f (1).txt"}
    client.login(namespace.owner.id)
    response = await client.post("/files/move", json=payload)
    message = "Can't move files inside Trash"
    assert response.json() == MalformedPath(message).as_dict()
    assert response.status_code == 400


async def test_move_but_path_is_recursive(client: TestClient, namespace: Namespace):
    payload = {"from_path": "a/b", "to_path": "a/b/c"}
    client.login(namespace.owner.id)
    response = await client.post("/files/move", json=payload)
    message = "Destination path should not start with source path"
    assert response.json() == MalformedPath(message).as_dict()
    assert response.status_code == 400


async def test_move_but_file_exists(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file_a = await file_factory(namespace.path, path="folder/file.txt")
    file_b = await file_factory(namespace.path, path="file.txt")
    payload = {"from_path": file_a.path, "to_path": file_b.path}
    client.login(namespace.owner.id)
    response = await client.post("/files/move", json=payload)
    assert response.status_code == 400
    assert response.json() == FileAlreadyExists(path=file_b.path).as_dict()


async def test_move_but_file_not_found(client: TestClient, namespace: Namespace):
    payload = {"from_path": "file_a.txt", "to_path": "file_b.txt"}
    client.login(namespace.owner.id)
    response = await client.post("/files/move", json=payload)
    assert response.status_code == 404
    assert response.json() == PathNotFound(path="file_a.txt").as_dict()


async def test_move_but_to_path_is_a_file(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file_a = await file_factory(namespace.path, path="file_a.txt")
    file_b = await file_factory(namespace.path, path="file_b.txt")
    payload = {"from_path": file_a.path, "to_path": f"{file_b.path}/{file_a.path}"}
    client.login(namespace.owner.id)
    response = await client.post("/files/move", json=payload)
    assert response.status_code == 400
    assert response.json() == NotADirectory(path=payload["to_path"]).as_dict()


async def test_move_but_path_missing_parent(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file_a = await file_factory(namespace.path, path="file_a.txt")
    payload = {"from_path": file_a.path, "to_path": f"folder/{file_a.path}"}
    client.login(namespace.owner.id)
    response = await client.post("/files/move", json=payload)
    message = "Some parents don't exist in the destination path"
    assert response.json() == MalformedPath(message).as_dict()
    assert response.status_code == 400


@pytest.mark.usefixtures("celery_session_worker")
async def test_move_batch(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    await file_factory(namespace.path, path='folder/a.txt')
    files = [await file_factory(namespace.path) for _ in range(3)]
    payload = {
        "items": [
            {"from_path": file.path, "to_path": f"folder/{file.path}"}
            for file in files
        ]
    }
    client.login(namespace.owner.id)
    response = await client.post("/files/move_batch", json=payload)
    assert "async_task_id" in response.json()
    assert response.status_code == 200

    task_id = response.json()["async_task_id"]
    task = tasks.celery_app.AsyncResult(task_id)
    results: list[FileTaskResult] = task.get(timeout=2)
    assert results[0].file is not None
    assert results[0].file.path.startswith("folder/")


@pytest.mark.usefixtures("celery_session_worker")
async def test_move_batch_check_task_is_pending(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path, path="folder/a.txt")
    relocations = [
        RelocationPath(from_path=file.path, to_path="folder/b.txt"),
        RelocationPath(from_path="c.txt", to_path="d.txt"),
    ]
    task = tasks.move_batch.delay(namespace, relocations)
    payload = {"async_task_id": task.id}

    client.login(namespace.owner.id)
    response = await client.post("/files/move_batch/check", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == 'pending'
    assert response.json()["result"] is None

    # sometimes there is a race condition between task and test teardown,
    # so ensure task is completed
    task.get(timeout=2)


@pytest.mark.usefixtures("celery_session_worker")
async def test_move_batch_check_task_is_completed(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path, path="folder/a.txt")
    relocations = [
        RelocationPath(from_path=file.path, to_path="folder/b.txt"),
        RelocationPath(from_path="c.txt", to_path="d.txt"),
    ]
    task = tasks.move_batch.delay(namespace, relocations)
    task.get(timeout=1)

    payload = {"async_task_id": task.id}
    client.login(namespace.owner.id)
    response = await client.post("/files/move_batch/check", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "completed"

    results = response.json()["result"]
    assert len(results) == 2

    assert results[0]["file"]["path"] == relocations[0].to_path
    assert results[0]["err_code"] is None

    assert results[1]["file"] is None
    assert results[1]["err_code"] == "file_not_found"


@pytest.mark.parametrize(["file_path", "path", "expected_path"], [
    ("file.txt", "file.txt", "Trash/file.txt"),  # move file to the Trash
    ("a/b/c/d.txt", "a/b", "Trash/b"),  # move folder to the Trash
])
async def test_move_to_trash(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
    file_path: str,
    path: str,
    expected_path: str,
):
    await file_factory(namespace.path, path=file_path)
    payload = {"path": path}
    client.login(namespace.owner.id)
    response = await client.post("/files/move_to_trash", json=payload)
    assert response.status_code == 200
    assert response.json()["path"] == expected_path


async def test_move_to_trash_but_it_is_a_trash(
    client: TestClient,
    namespace: Namespace,
):
    payload = {"path": "Trash"}
    client.login(namespace.owner.id)
    response = await client.post("/files/move_to_trash", json=payload)
    message = "Can't move Trash into itself"
    assert response.json() == MalformedPath(message).as_dict()
    assert response.status_code == 400


async def test_move_to_trash_but_file_is_in_trash(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path, path="Trash/file.txt")
    payload = {"path": file.path}
    client.login(namespace.owner.id)
    response = await client.post("/files/move_to_trash", json=payload)
    assert response.status_code == 400
    assert response.json() == FileAlreadyDeleted(path=file.path).as_dict()


async def test_move_to_trash_but_file_not_found(
    client: TestClient,
    namespace: Namespace,
):
    payload = {"path": "file.txt"}
    client.login(namespace.owner.id)
    response = await client.post("/files/move_to_trash", json=payload)
    assert response.status_code == 404
    assert response.json() == PathNotFound(path=payload["path"]).as_dict()


@pytest.mark.usefixtures("celery_session_worker")
async def test_move_to_trash_batch(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    files = [await file_factory(namespace.path) for _ in range(3)]
    payload = {
        "items": [
            {"path": file.path} for file in files
        ],
    }
    client.login(namespace.owner.id)
    response = await client.post("/files/move_to_trash_batch", json=payload)
    assert "async_task_id" in response.json()
    assert response.status_code == 200

    task_id = response.json()["async_task_id"]
    task = tasks.celery_app.AsyncResult(task_id)
    results: list[FileTaskResult] = task.get(timeout=2)
    assert results[0].file is not None
    assert results[0].file.path.startswith("Trash/")


@pytest.mark.parametrize(["path", "expected_path", "updates_count"], [
    (b"folder/file.txt", "folder/file.txt", 2),
    (b"./f.txt", "f.txt", 1),
])
async def test_upload(
    client: TestClient,
    namespace: Namespace,
    path: str,
    expected_path: str,
    updates_count: int,
):
    payload = {
        "file": BytesIO(b"Dummy file"),
        "path": (None, path),
    }
    client.login(namespace.owner.id)
    response = await client.post("/files/upload", files=payload)  # type: ignore
    assert response.status_code == 200
    assert response.json()["file"]["path"] == expected_path
    assert len(response.json()["updates"]) == updates_count


async def test_upload_but_to_a_special_path(client: TestClient, namespace: Namespace):
    payload = {
        "file": BytesIO(b"Dummy file"),
        "path": (None, b"Trash"),
    }
    client.login(namespace.owner.id)
    response = await client.post("/files/upload", files=payload)  # type: ignore
    message = "Uploads to the Trash are not allowed"
    assert response.json() == MalformedPath(message).as_dict()
    assert response.status_code == 400


async def test_upload_but_path_is_a_file(
    client: TestClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path, path="f.txt")
    payload = {
        "file": BytesIO(b"Dummy file"),
        "path": (None, f"{file.path}/dummy".encode()),
    }
    client.login(namespace.owner.id)
    response = await client.post("/files/upload", files=payload)  # type: ignore
    assert response.json() == NotADirectory(path=f"{file.path}/dummy").as_dict()
    assert response.status_code == 400


async def test_upload_but_max_upload_size_is_exceeded(
    client: TestClient,
    namespace: Namespace,
):
    payload = {
        "file": BytesIO(b"Dummy file"),
        "path": (None, b"folder/file.txt"),
    }
    client.login(namespace.owner.id)
    with mock.patch("app.config.FEATURES_UPLOAD_FILE_MAX_SIZE", 5):
        response = await client.post("/files/upload", files=payload)  # type: ignore
    assert response.json() == UploadFileTooLarge().as_dict()
    assert response.status_code == 400


async def test_upload_but_storage_quota_is_exceeded(
    client: TestClient,
    namespace: Namespace,
    account_factory: AccountFactory,
    file_factory: FileFactory,
):
    text = b"Dummy file"
    content = BytesIO(text)
    await account_factory(user=namespace.owner, storage_quota=len(text) * 2 - 1)
    await file_factory(namespace.path, content=content)
    payload = {
        "file": content,
        "path": (None, b"folder/file.txt"),
    }
    client.login(namespace.owner.id)
    response = await client.post("/files/upload", files=payload)  # type: ignore
    assert response.json() == StorageQuotaExceeded().as_dict()
    assert response.status_code == 400
