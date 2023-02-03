from __future__ import annotations

import os.path
import secrets
import urllib.parse
import uuid
from io import BytesIO
from tempfile import SpooledTemporaryFile
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app import config, errors, tasks
from app.api import shortcuts
from app.api.files.exceptions import (
    DownloadNotFound,
    FileAlreadyExists,
    MalformedPath,
    NotADirectory,
    PathNotFound,
    StorageQuotaExceeded,
    UploadFileTooLarge,
)
from app.domain.entities import File, Folder
from app.entities import Exif, RelocationPath

if TYPE_CHECKING:
    from unittest.mock import AsyncMock, MagicMock

    from fastapi import FastAPI

    from app.api.exceptions import APIError
    from app.entities import FileTaskResult, Namespace
    from tests.conftest import TestClient
    from tests.factories import (
        FileFactory,
        FileMetadataFactory,
        FingerprintFactory,
    )

pytestmark = [pytest.mark.asyncio, pytest.mark.database(transaction=True)]


class TestCreateFolder:
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
        folder = Folder(
            id=uuid.uuid4(),
            ns_path=str(namespace.path),
            name=expected_path.split('/')[-1],
            path=expected_path,
        )
        ns_service.create_folder.return_value = folder
        payload = {"path": path}
        client.login(namespace.owner.id)
        response = await client.post("/files/create_folder", json=payload)
        assert response.json()["id"] == str(folder.id)
        assert response.json()["name"] == folder.name
        assert response.json()["path"] == folder.path
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


class TestMoveBatch:
    @pytest.fixture
    def move_batch(self):
        with mock.patch("app.tasks.move_batch") as patch:
            yield patch

    async def test(
        self, client: TestClient, namespace: Namespace, move_batch: MagicMock,
    ):
        expected_task_id = uuid.uuid4()
        move_batch.delay.return_value = mock.Mock(id=expected_task_id)
        payload = {
            "items": [
                {"from_path": f"{i}.txt", "to_path": f"folder/{i}.txt"}
                for i in range(3)
            ]
        }
        client.login(namespace.owner.id)
        response = await client.post("/files/move_batch", json=payload)
        assert "async_task_id" in response.json()
        assert response.status_code == 200

        task_id = response.json()["async_task_id"]
        assert task_id == str(expected_task_id)


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
    task = tasks.move_batch.delay(namespace.path, relocations)
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
    task = tasks.move_batch.delay(namespace.path, relocations)
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


class TestMoveToTrashBatch:
    @pytest.fixture
    def move_to_trash_batch(self):
        with mock.patch("app.tasks.move_to_trash_batch") as patch:
            yield patch

    async def test(
        self, client: TestClient, namespace: Namespace, move_to_trash_batch: MagicMock,
    ):
        expected_task_id = uuid.uuid4()
        move_to_trash_batch.delay.return_value = mock.Mock(id=expected_task_id)
        payload = {
            "items": [
                {"path": f"{i}.txt"} for i in range(3)
            ]
        }
        client.login(namespace.owner.id)
        response = await client.post("/files/move_to_trash_batch", json=payload)
        assert "async_task_id" in response.json()
        assert response.status_code == 200

        task_id = response.json()["async_task_id"]
        assert task_id == str(expected_task_id)


class TestUpload:
    @pytest.fixture
    def upload_file(self, app: FastAPI):
        usecase = app.state.provider.usecase
        upload_file_mock = mock.AsyncMock(usecase.upload_file)
        with mock.patch.object(usecase, "upload_file", upload_file_mock) as mocked:
            yield mocked

    @staticmethod
    def make_file(ns_path: str, path: str, size: int) -> File:
        return File(
            id=uuid.uuid4(),
            ns_path=ns_path,
            name=os.path.basename(path),
            path=path,
            size=size,
            mediatype="plain/text",
        )

    @pytest.mark.parametrize(["path", "expected_path"], [
        (b"folder/file.txt", "folder/file.txt"),
        (b"./f.txt", "f.txt"),
    ])
    async def test(
        self,
        client: TestClient,
        namespace: Namespace,
        upload_file: AsyncMock,
        path: str,
        expected_path: str,
    ):
        ns_path = str(namespace.path)
        content = BytesIO(b"Dummy file")
        size = len(content.getvalue())
        upload_file.return_value = self.make_file(ns_path, expected_path, size=size)
        payload = {
            "file": content,
            "path": (None, path),
        }
        client.login(namespace.owner.id)
        response = await client.post("/files/upload", files=payload)  # type: ignore
        assert response.status_code == 200
        assert response.json()["path"] == expected_path
        assert upload_file.await_args is not None
        assert len(upload_file.await_args.args) == 3
        assert upload_file.await_args.args[:2] == (ns_path, expected_path)
        assert isinstance(upload_file.await_args.args[2], SpooledTemporaryFile)

    @pytest.mark.parametrize(["path", "error", "expected_error"], [
        ("Trash", errors.MalformedPath("Bad path"), MalformedPath("Bad path")),
        ("f.txt/file", errors.NotADirectory(), NotADirectory(path="f.txt/file")),
        ("f.txt", errors.FileTooLarge(), UploadFileTooLarge()),
        ("f.txt", errors.StorageQuotaExceeded(), StorageQuotaExceeded()),
    ])
    async def test_reraising_app_errors_to_api_errors(
        self,
        client: TestClient,
        namespace: Namespace,
        upload_file: AsyncMock,
        path: str,
        error: errors.Error,
        expected_error: APIError,
    ):
        upload_file.side_effect = error
        payload = {
            "file": BytesIO(b"Dummy file"),
            "path": (None, path.encode()),
        }
        client.login(namespace.owner.id)
        response = await client.post("/files/upload", files=payload)  # type: ignore
        assert response.json() == expected_error.as_dict()
        assert response.status_code == 400
        upload_file.assert_awaited_once()
