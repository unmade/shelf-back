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
    from app.app.files.domain.file_member import FileMemberActions
    from app.app.files.services import FileMemberService

pytestmark = [pytest.mark.anyio]


def _make_file(
    ns_path: str, path: AnyPath, size: int = 10, mediatype: str = "plain/text"
) -> File:
    path = Path(path)
    return File(
        id=uuid.uuid4(),
        ns_path=ns_path,
        name=path.name,
        path=path,
        chash=uuid.uuid4().hex,
        size=size,
        mediatype=mediatype,
    )


def _make_file_member(
    file: File,
    user: User,
    actions: FileMemberActions = FileMember.EDITOR,
) -> FileMember:
    return FileMember(
        file_id=file.id,
        actions=actions,
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
        db = cast(mock.MagicMock, file_member_service.db)
        # WHEN
        member = await file_member_service.add(file.id, user.id, FileMember.EDITOR)
        # THEN
        assert member == db.file_member.save.return_value
        db.file_member.save.assert_awaited_once_with(
            FileMember.model_construct(
                file_id=file.id,
                actions=FileMember.EDITOR,
                created_at=mock.ANY,
                user=FileMember.User(
                    id=user.id,
                    username="",
                ),
            )
        )


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
            _make_file_member(file, owner, actions=FileMember.OWNER),
            _make_file_member(file, _make_user("user")),
        ]
        db = cast(mock.MagicMock, file_member_service.db)
        db.file_member.list_by_file_id_batch.return_value = expected_members
        # WHEN
        members = await file_member_service.list_all(file.id)
        # THEN
        assert members == expected_members
        db.file_member.list_by_file_id_batch.assert_awaited_once_with([file.id])


class TestListByFileIdBatch:
    async def test(self, file_member_service: FileMemberService):
        # GIVEN
        admin, user = _make_user("admin"), _make_user("user")
        files = [_make_file("admin", "f.txt"), _make_file("user", "f.txt")]
        file_ids = [file.id for file in files]
        members = [
            _make_file_member(files[0], admin, actions=FileMember.OWNER),
            _make_file_member(files[1], user, actions=FileMember.OWNER),
            _make_file_member(files[1], admin, actions=FileMember.EDITOR),
        ]
        db = cast(mock.MagicMock, file_member_service.db)
        db.file_member.list_by_file_id_batch.return_value = members
        # WHEN
        result = await file_member_service.list_by_file_id_batch(file_ids)
        # THEN
        assert result == {files[0].id: members[:1], files[1].id: members[1:]}
        db.file_member.list_by_file_id_batch.assert_awaited_once_with(file_ids)


class TestListByUserID:
    async def test(self, file_member_service: FileMemberService):
        # GIVEN
        user, limit = _make_user("admin"), 10
        file_a, file_b = _make_file("admin", "f.txt"), _make_file("user", "f.txt")
        expected_members = [
            _make_file_member(file_a, user, actions=FileMember.OWNER),
            _make_file_member(file_b, user, actions=FileMember.EDITOR),
        ]
        db = cast(mock.MagicMock, file_member_service.db)
        db.file_member.list_by_user_id.return_value = expected_members
        # WHEN
        members = await file_member_service.list_by_user_id(user.id, limit=limit)
        # THEN
        assert members == expected_members
        db.file_member.list_by_user_id.assert_awaited_once_with(user.id, limit=limit)


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
