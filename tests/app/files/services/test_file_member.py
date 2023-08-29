from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.files.domain import File, FileMember, Path
from app.app.files.repositories.file_member import FileMemberUpdate
from app.app.users.domain import User

if TYPE_CHECKING:
    from app.app.files.domain import AnyPath
    from app.app.files.services import FileMemberService

pytestmark = [pytest.mark.asyncio]


def _make_file(
    ns_path: str, path: AnyPath, size: int = 10, mediatype: str = "plain/text"
) -> File:
    path = Path(path)
    return File(
        id=uuid.uuid4(),
        ns_path=ns_path,
        name=path.name,
        path=path,
        size=size,
        mediatype=mediatype,
    )


def _make_file_member(
    file: File,
    user: User,
    is_owner: bool = False,
) -> FileMember:
    return FileMember(
        file_id=file.id,
        owner=is_owner,
        actions=FileMember.EDITOR,
        user=FileMember.User(
            id=user.id,
            username=user.username,
        ),
    )


def _make_user(username: str) -> User:
    return User(
        id=uuid.uuid4(),
        username=username,
        password="root",
    )


class TestAdd:
    async def test(self, file_member_service: FileMemberService):
        # GIVEN
        file, user = _make_file("admin", "f.txt"), _make_user("user")
        filecore = cast(mock.MagicMock, file_member_service.filecore)
        filecore.get_by_id.return_value = file
        db = cast(mock.MagicMock, file_member_service.db)
        db.user.get_by_username.return_value = _make_user(file.ns_path)
        # WHEN
        member = await file_member_service.add(file.id, user.id, FileMember.EDITOR)
        # THEN
        assert member == db.file_member.save.return_value
        filecore.get_by_id.assert_awaited_once_with(file.id)
        db.user.get_by_username.assert_awaited_once_with(file.ns_path)
        db.file_member.save.assert_awaited_once_with(
            FileMember(
                file_id=file.id,
                actions=FileMember.EDITOR,
                user=FileMember.User(
                    id=user.id,
                    username="",
                ),
            )
        )

    async def test_when_adding_an_owner(self, file_member_service: FileMemberService):
        # GIVEN
        file, owner = _make_file("admin", "f.txt"), _make_user("admin")
        filecore = cast(mock.MagicMock, file_member_service.filecore)
        filecore.get_by_id.return_value = file
        db = cast(mock.MagicMock, file_member_service.db)
        db.user.get_by_username.return_value = owner
        # WHEN
        with pytest.raises(FileMember.AlreadyExists):
            await file_member_service.add(file.id, owner.id, FileMember.EDITOR)
        # THEN
        db.file_member.save.assert_not_awaited()
        filecore.get_by_id.assert_awaited_once_with(file.id)
        db.user.get_by_username.assert_awaited_once_with(file.ns_path)


class TestGet:
    async def test(self, file_member_service: FileMemberService):
        # GIVEN
        file_id, user_id = uuid.uuid4(), uuid.uuid4()
        db = cast(mock.MagicMock, file_member_service.db)
        # WHEN
        result = await file_member_service.get(file_id, user_id)
        # THEN
        member = db.file_member.get.return_value
        assert result == member
        db.file_member.get.assert_awaited_once_with(file_id, user_id)


class TestListAll:
    async def test(self, file_member_service: FileMemberService):
        # GIVEN
        file, owner = _make_file("admin", "f.txt"), _make_user("admin")
        expected_members = [
            _make_file_member(file, owner, is_owner=True),
            _make_file_member(file, _make_user("user")),
        ]
        filecore = cast(mock.MagicMock, file_member_service.filecore)
        filecore.get_by_id.return_value = file
        db = cast(mock.MagicMock, file_member_service.db)
        db.file_member.list_all.return_value = [expected_members[1]]
        db.user.get_by_username.return_value = owner

        # WHEN
        members = await file_member_service.list_all(file.id)
        # THEN
        assert members == expected_members
        db.file_member.list_all.assert_awaited_once_with(file.id)
        filecore.get_by_id.assert_awaited_once_with(file.id)
        db.user.get_by_username.assert_awaited_once_with(file.ns_path)


class TestRemove:
    async def test(self, file_member_service: FileMemberService):
        # GIVEN
        file_id, user_id = uuid.uuid4(), uuid.uuid4()
        db = cast(mock.MagicMock, file_member_service.db)
        # WHEN
        await file_member_service.remove(file_id, user_id)
        # THEN
        db.file_member.delete.assert_awaited_once_with(file_id, user_id)


class TestSetActions:
    async def test(self, file_member_service: FileMemberService):
        # GIVEN
        file_id, user_id = uuid.uuid4(), uuid.uuid4()
        actions = FileMember.VIEWER
        db = cast(mock.MagicMock, file_member_service.db)
        # WHEN
        result = await file_member_service.set_actions(
            file_id, user_id, actions=actions
        )
        # THEN
        assert result == db.file_member.update.return_value
        db.file_member.get.assert_awaited_once_with(file_id, user_id)
        member = db.file_member.get.return_value
        db.file_member.update.assert_awaited_once_with(
            member, FileMemberUpdate(actions=actions)
        )
