from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.app.files.domain import File, FileMember, Namespace
from app.app.users.domain import User
from app.infrastructure.database.edgedb.db import db_context
from app.infrastructure.database.edgedb.repositories.file_member import PermissionFlag

if TYPE_CHECKING:
    from app.infrastructure.database.edgedb.repositories import FileMemberRepository

    from ..conftest import FileFactory, FileMemberFactory, UserFactory

pytestmark = [pytest.mark.asyncio, pytest.mark.database]


async def _list_members(file_id: str):
    query = """
        SELECT
            FileMember {
                permissions,
                file: { id },
                user: { id, username },
            }
        FILTER
            .file.id = <uuid>$file_id
    """
    objs = await db_context.get().query(query, file_id=file_id)
    return [
        FileMember(
            file_id=str(obj.file.id),
            access_level=FileMember.AccessLevel.editor,
            permissions=PermissionFlag.load(obj.permissions),
            user=FileMember.User(
                id=obj.user.id,
                username=obj.user.username,
            )
        )
        for obj in objs
    ]


class TestListAll:
    async def test(
        self,
        file_member_repo: FileMemberRepository,
        file_factory: FileFactory,
        file_member_factory: FileMemberFactory,
        user_factory: UserFactory,
        namespace: Namespace,
    ):
        # GIVEN
        file = await file_factory(namespace.path)
        users = [await user_factory(), await user_factory()]
        members = [
            await file_member_factory(file_id=file.id, user_id=user.id)
            for user in users
        ]
        # WHEN
        result = await file_member_repo.list_all(file.id)
        # THEN
        assert result == members

    async def test_when_no_members(
        self,
        file_member_repo: FileMemberRepository,
        file_factory: FileFactory,
        namespace: Namespace,
    ):
        file = await file_factory(namespace.path)
        result = await file_member_repo.list_all(file.id)
        assert result == []

    async def test_when_file_does_not_exist(
        self,
        file_member_repo: FileMemberRepository,
    ):
        file_id = str(uuid.uuid4())
        result = await file_member_repo.list_all(file_id)
        assert result == []


class TestSave:
    async def test(
        self, file_member_repo: FileMemberRepository, file: File, user: User
    ):
        # GIVEN
        member = FileMember(
            file_id=file.id,
            access_level=FileMember.AccessLevel.editor,
            permissions=FileMember.EDITOR,
            user=FileMember.User(
                id=user.id,
                username="",
            )
        )
        # WHEN
        saved_member = await file_member_repo.save(member)
        # THEN
        members = await _list_members(saved_member.file_id)
        assert [saved_member] == members
        assert saved_member.user.username == user.username

    async def test_adding_twice(
        self, file_member_repo: FileMemberRepository, file: File, user: User
    ):
        # GIVEN
        member = FileMember(
            file_id=file.id,
            access_level=FileMember.AccessLevel.owner,
            permissions=FileMember.EDITOR,
            user=FileMember.User(
                id=user.id,
                username="",
            )
        )
        await file_member_repo.save(member)
        # WHEN
        with pytest.raises(FileMember.AlreadyExists):
            await file_member_repo.save(member)

    async def test_when_file_does_not_exist(
        self, file_member_repo: FileMemberRepository, user: User
    ):
        # GIVEN
        member = FileMember(
            file_id=str(uuid.uuid4()),
            access_level=FileMember.AccessLevel.viewer,
            permissions=FileMember.EDITOR,
            user=FileMember.User(
                id=user.id,
                username="",
            )
        )
        # WHEN
        with pytest.raises(File.NotFound):
            await file_member_repo.save(member)

    async def test_when_user_does_not_exist(
        self, file_member_repo: FileMemberRepository, file: File
    ):
        # GIVEN
        member = FileMember(
            file_id=file.id,
            access_level=FileMember.AccessLevel.viewer,
            permissions=FileMember.EDITOR,
            user=FileMember.User(
                id=uuid.uuid4(),
                username="",
            )
        )
        # WHEN
        with pytest.raises(User.NotFound):
            await file_member_repo.save(member)
