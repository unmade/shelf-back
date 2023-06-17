from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.files.domain import FileMember

if TYPE_CHECKING:
    from app.app.files.services import FileMemberService

pytestmark = [pytest.mark.asyncio]


class TestAdd:
    async def test(self, file_member_service: FileMemberService):
        # GIVEN
        user_id, file_id = uuid.uuid4(), str(uuid.uuid4())
        db = cast(mock.MagicMock, file_member_service.db)
        # WHEN
        member = await file_member_service.add(file_id, user_id)
        # THEN
        assert member == db.file_member.save.return_value
        db.file_member.save.assert_awaited_once_with(
            FileMember(
                file_id=file_id,
                user=FileMember.User(
                    id=user_id,
                    username="",
                ),
            )
        )


class TestListAll:
    async def test(self, file_member_service: FileMemberService):
        # GIVEN
        file_id = str(uuid.uuid4())
        db = cast(mock.MagicMock, file_member_service.db)
        # WHEN
        members = await file_member_service.list_all(file_id)
        # THEN
        assert members == db.file_member.list_all.return_value
        db.file_member.list_all.assert_awaited_once_with(file_id)
