from __future__ import annotations

from io import BytesIO
from unittest import mock

import pytest

from app import errors
from app.app.services import NamespaceService, UserService
from app.app.usecases import UploadFile
from app.domain.entities import Account

pytestmark = [pytest.mark.asyncio]


class TestUploadFile:
    async def test_unlimited_storage_quota(self) -> None:
        user_service = mock.MagicMock(UserService)
        ns_service = mock.MagicMock(NamespaceService)
        upload = UploadFile(namespace_service=ns_service, user_service=user_service)

        user_service.get_account = mock.AsyncMock(
            return_value=mock.MagicMock(Account, storage_quota=None)
        )

        content = BytesIO(b"Dummy file")
        file = await upload("admin", "f.txt", content=content)
        assert file == ns_service.add_file.return_value
        ns_service.add_file.assert_awaited_once_with("admin", "f.txt", content)

        owner_id = ns_service.get_by_path.return_value.owner_id
        user_service.get_account.assert_awaited_once_with(owner_id)
        ns_service.get_space_used_by_owner_id.assert_not_awaited()

    async def test_limited_storage_quota(self) -> None:
        user_service = mock.MagicMock(UserService)
        ns_service = mock.MagicMock(NamespaceService)
        upload = UploadFile(namespace_service=ns_service, user_service=user_service)

        user_service.get_account = mock.AsyncMock(
            return_value=mock.MagicMock(Account, storage_quota=1024)
        )
        ns_service.get_space_used_by_owner_id = mock.AsyncMock(return_value=512)

        content = BytesIO(b"Dummy file")
        file = await upload("admin", "f.txt", content=content)
        assert file == ns_service.add_file.return_value
        ns_service.add_file.assert_awaited_once_with("admin", "f.txt", content)

        owner_id = ns_service.get_by_path.return_value.owner_id
        user_service.get_account.assert_awaited_once_with(owner_id)
        ns_service.get_space_used_by_owner_id.assert_awaited_once_with(owner_id)

    async def test_when_uploading_to_trash_folder(self) -> None:
        user_service = mock.MagicMock(UserService)
        ns_service = mock.MagicMock(NamespaceService)
        upload = UploadFile(namespace_service=ns_service, user_service=user_service)

        content = BytesIO(b"Dummy file")
        with pytest.raises(errors.MalformedPath) as excinfo:
            await upload("admin", "Trash/f.txt", content=content)
        assert str(excinfo.value) == "Uploads to the Trash folder are not allowed"
        ns_service.add_file.assert_not_awaited()
        ns_service.get_by_path.assert_not_awaited()
        user_service.get_account.assert_not_awaited()
        ns_service.get_space_used_by_owner_id.assert_not_awaited()

    async def test_when_max_upload_size_limit_is_exceeded(self):
        user_service = mock.MagicMock(UserService)
        ns_service = mock.MagicMock(NamespaceService)
        upload = UploadFile(namespace_service=ns_service, user_service=user_service)

        content = BytesIO(b"Dummy file")
        with (
            mock.patch("app.config.FEATURES_UPLOAD_FILE_MAX_SIZE", 5),
            pytest.raises(errors.FileTooLarge),
        ):
            await upload("admin", "f.txt", content=content)
        ns_service.add_file.assert_not_awaited()
        ns_service.get_by_path.assert_not_awaited()
        user_service.get_account.assert_not_awaited()
        ns_service.get_space_used_by_owner_id.assert_not_awaited()

    async def test_when_exceeding_storage_quota_limit(self) -> None:
        user_service = mock.MagicMock(UserService)
        ns_service = mock.MagicMock(NamespaceService)
        upload = UploadFile(namespace_service=ns_service, user_service=user_service)

        user_service.get_account = mock.AsyncMock(
            return_value=mock.MagicMock(Account, storage_quota=1024)
        )
        ns_service.get_space_used_by_owner_id = mock.AsyncMock(return_value=1024)

        content = BytesIO(b"Dummy file")
        with pytest.raises(errors.StorageQuotaExceeded):
            await upload("admin", "f.txt", content=content)
        ns_service.add_file.assert_not_awaited()

        owner_id = ns_service.get_by_path.return_value.owner_id
        user_service.get_account.assert_awaited_once_with(owner_id)
        ns_service.get_space_used_by_owner_id.assert_awaited_once_with(owner_id)
