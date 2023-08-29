from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.audit.domain import AuditTrail, CurrentUserContext
from app.app.audit.domain.current_user_context import current_user_ctx
from app.app.files.domain import File, Path
from app.app.infrastructure.database import SENTINEL_ID
from app.app.users.domain import User

if TYPE_CHECKING:
    from app.app.audit.services import AuditTrailService
    from app.app.files.domain import AnyPath

pytestmark = [pytest.mark.asyncio]

now = datetime.datetime(2023, 4, 15, 22, 51)


def _make_user(username: str):
    return User(
        id=uuid.uuid4(),
        username=username,
        password="root",
    )



def _make_file(ns_path: str, path: AnyPath) -> File:
    return File(
        id=uuid.uuid4(),
        ns_path=ns_path,
        name=Path(path).name,
        path=path,
        size=10,
        mediatype="plain/text",
    )


class TestTrackFileAction:
    async def test(self, audit_trail_service: AuditTrailService):
        # GIVEN
        user = _make_user("admin")
        file = _make_file("admin", "folder/f.txt")
        current_user_ctx.set(CurrentUserContext(user=user.model_dump()))
        db = cast(mock.MagicMock, audit_trail_service.db)
        # WHEN
        await audit_trail_service._track_file_action(
            AuditTrail.Action.file_added,
            file=file,
        )
        # THEN
        db.audit_trail.save.assert_awaited_once_with(
            AuditTrail.model_construct(
                id=SENTINEL_ID,
                action=AuditTrail.Action.file_added,
                user=AuditTrail.User(
                    id=str(user.id),
                    username=user.username,
                ),
                asset=AuditTrail.File(
                    id=file.id,
                    name=file.name,
                    path=str(file.path),
                ),
                created_at=mock.ANY,
            )
        )


class TestTrackUserAction:
    async def test(self, audit_trail_service: AuditTrailService):
        # GIVEN
        user = _make_user("admin")
        current_user_ctx.set(CurrentUserContext(user=user.model_dump()))
        db = cast(mock.MagicMock, audit_trail_service.db)
        # WHEN
        await audit_trail_service._track_user_action(
            AuditTrail.Action.trash_emptied,
        )
        # THEN
        db.audit_trail.save.assert_awaited_once_with(
            AuditTrail.model_construct(
                id=SENTINEL_ID,
                action=AuditTrail.Action.trash_emptied,
                user=AuditTrail.User(
                    id=str(user.id),
                    username=user.username,
                ),
                created_at=mock.ANY,
            )
        )


class TestFileAdded:
    async def test(self, audit_trail_service: AuditTrailService):
        # GIVEN
        file = _make_file("admin", "f.txt")
        service_cls = audit_trail_service.__class__
        # WHEN
        with mock.patch.object(service_cls, "_track_file_action") as patch:
            await audit_trail_service.file_added(file=file)
        # THEN
        patch.assert_awaited_once_with(AuditTrail.Action.file_added, file=file)


class TestFileMoved:
    async def test(self, audit_trail_service: AuditTrailService):
        # GIVEN
        file = _make_file("admin", "f.txt")
        service_cls = audit_trail_service.__class__
        # WHEN
        with mock.patch.object(service_cls, "_track_file_action") as patch:
            await audit_trail_service.file_moved(file=file)
        # THEN
        patch.assert_awaited_once_with(AuditTrail.Action.file_moved, file=file)


class TestFileTrashed:
    async def test(self, audit_trail_service: AuditTrailService):
        # GIVEN
        file = _make_file("admin", "f.txt")
        service_cls = audit_trail_service.__class__
        # WHEN
        with mock.patch.object(service_cls, "_track_file_action") as patch:
            await audit_trail_service.file_trashed(file=file)
        # THEN
        patch.assert_awaited_once_with(AuditTrail.Action.file_trashed, file=file)


class TestFolderCreated:
    async def test(self, audit_trail_service: AuditTrailService):
        # GIVEN
        file = _make_file("admin", "f.txt")
        service_cls = audit_trail_service.__class__
        # WHEN
        with mock.patch.object(service_cls, "_track_file_action") as patch:
            await audit_trail_service.folder_created(file=file)
        # THEN
        patch.assert_awaited_once_with(AuditTrail.Action.folder_created, file=file)


class TestTrashEmptied:
    async def test(self, audit_trail_service: AuditTrailService):
        # GIVEN
        service_cls = audit_trail_service.__class__
        # WHEN
        with mock.patch.object(service_cls, "_track_user_action") as patch:
            await audit_trail_service.trash_emptied()
        # THEN
        patch.assert_awaited_once_with(AuditTrail.Action.trash_emptied)


class TestUserSignedIn:
    async def test(self, audit_trail_service: AuditTrailService):
        # GIVEN
        user = _make_user("admin")
        db = cast(mock.MagicMock, audit_trail_service.db)
        # WHEN
        await audit_trail_service.user_signed_in(user=user)
        # THEN
        db.audit_trail.save.assert_awaited_once_with(
            AuditTrail.model_construct(
                id=SENTINEL_ID,
                action=AuditTrail.Action.user_signed_in,
                user=AuditTrail.User(
                    id=str(user.id),
                    username=user.username,
                ),
                created_at=mock.ANY,
            )
        )
