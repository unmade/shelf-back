from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.app.files.domain import File, FileMember, Namespace
from app.app.files.repositories.file_member import FileMemberUpdate
from app.app.users.domain import User
from app.infrastructure.database.edgedb.db import db_context
from app.infrastructure.database.edgedb.repositories.file_member import ActionFlag

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.files.domain.file_member import FileMemberActions
    from app.infrastructure.database.edgedb.repositories import FileMemberRepository
    from tests.infrastructure.database.edgedb.conftest import (
        FileFactory,
        FileMemberFactory,
        UserFactory,
    )

pytestmark = [pytest.mark.asyncio, pytest.mark.database]


async def _get(file_id: UUID, user_id: UUID) -> FileMember:
    query = """
        SELECT
            FileMember {
                actions,
                created_at,
                file: { id },
                user: { id, username },
            }
        FILTER
            .file.id = <uuid>$file_id
            AND
            .user.id = <uuid>$user_id
        LIMIT 1
    """
    obj = await db_context.get().query_required_single(
        query,
        file_id=file_id,
        user_id=user_id,
    )
    return FileMember(
        file_id=obj.file.id,
        actions=ActionFlag.load(obj.actions),
        created_at=obj.created_at,
        user=FileMember.User(
            id=obj.user.id,
            username=obj.user.username,
        )
    )


async def _list_members(file_id: UUID):
    query = """
        SELECT
            FileMember {
                actions,
                created_at,
                file: { id },
                user: { id, username },
            }
        FILTER
            .file.id = <uuid>$file_id
    """
    objs = await db_context.get().query(query, file_id=file_id)
    return [
        FileMember(
            file_id=obj.file.id,
            actions=ActionFlag.load(obj.actions),
            created_at=obj.created_at,
            user=FileMember.User(
                id=obj.user.id,
                username=obj.user.username,
            )
        )
        for obj in objs
    ]


class TestActionFlag:
    @pytest.mark.parametrize(["given", "expected"], [
        (FileMember.Actions(), 0),
        (FileMember.VIEWER, 3),
        (FileMember.EDITOR, 63),
    ])
    async def test(self, given: FileMemberActions, expected: int):
        assert ActionFlag.dump(given) == expected


class TestDelete:
    async def test(
        self,
        file_member_repo: FileMemberRepository,
        file_member_factory: FileMemberFactory,
        file: File,
        user_b: User,
    ):
        # GIVEN
        await file_member_factory(file_id=file.id, user_id=user_b.id)
        # WHEN
        await file_member_repo.delete(file.id, user_b.id)
        # THEN
        assert await _list_members(file.id) == []


class TestGet:
    async def test(
        self,
        file_member_repo: FileMemberRepository,
        file_member_factory: FileMemberFactory,
        file: File,
        user_b: User,
    ):
        # GIVEN
        await file_member_factory(file_id=file.id, user_id=user_b.id)
        # WHEN
        member = await file_member_repo.get(file.id, user_b.id)
        # THEN
        assert member == await _get(file.id, user_b.id)

    async def test_when_member_not_found(
        self,
        file_member_repo: FileMemberRepository,
    ):
        # GIVEN
        file_id, user_id = uuid.uuid4(), uuid.uuid4()
        # WHEN
        with pytest.raises(FileMember.NotFound):
            await file_member_repo.get(file_id, user_id)


class TestListByFileIdBatch:
    async def test(
        self,
        file_member_repo: FileMemberRepository,
        file_factory: FileFactory,
        file_member_factory: FileMemberFactory,
        user_factory: UserFactory,
        namespace: Namespace,
    ):
        # GIVEN
        files = [await file_factory(namespace.path), await file_factory(namespace.path)]
        users = [await user_factory(), await user_factory()]
        members = [
            await file_member_factory(file_id=files[0].id, user_id=users[0].id),
            await file_member_factory(file_id=files[0].id, user_id=users[1].id),
            await file_member_factory(file_id=files[1].id, user_id=users[0].id),
        ]
        # WHEN
        result = await file_member_repo.list_by_file_id_batch(file.id for file in files)
        # THEN
        assert result == members

    async def test_when_no_members(
        self,
        file_member_repo: FileMemberRepository,
        file_factory: FileFactory,
        namespace: Namespace,
    ):
        file = await file_factory(namespace.path)
        result = await file_member_repo.list_by_file_id_batch([file.id])
        assert result == []

    async def test_when_file_does_not_exist(
        self,
        file_member_repo: FileMemberRepository,
    ):
        file_id = uuid.uuid4()
        result = await file_member_repo.list_by_file_id_batch([file_id])
        assert result == []


class TestListByUserID:
    async def test(
        self,
        file_member_repo: FileMemberRepository,
        file_factory: FileFactory,
        file_member_factory: FileMemberFactory,
        user_factory: UserFactory,
        namespace: Namespace,
    ):
        # GIVEN
        files = [await file_factory(namespace.path), await file_factory(namespace.path)]
        users = [await user_factory(), await user_factory()]
        members = [
            await file_member_factory(file_id=files[0].id, user_id=users[0].id),
            await file_member_factory(file_id=files[0].id, user_id=users[1].id),
            await file_member_factory(file_id=files[1].id, user_id=users[0].id),
        ]
        # WHEN
        result = await file_member_repo.list_by_user_id(users[0].id)
        # THEN
        assert result == [members[0], members[2]]

        # WHEN
        result = await file_member_repo.list_by_user_id(users[1].id)
        # THEN
        assert result == [members[1]]

    async def test_when_no_members(
        self,
        file_member_repo: FileMemberRepository,
        file_factory: FileFactory,
        namespace: Namespace,
        user: User,
    ):
        await file_factory(namespace.path)
        result = await file_member_repo.list_by_user_id(user.id)
        assert result == []

    async def test_when_user_does_not_exist(
        self,
        file_member_repo: FileMemberRepository,
    ):
        user_id = uuid.uuid4()
        result = await file_member_repo.list_by_user_id(user_id)
        assert result == []



class TestSave:
    async def test(
        self, file_member_repo: FileMemberRepository, file: File, user: User
    ):
        # GIVEN
        member = FileMember(
            file_id=file.id,
            actions=FileMember.EDITOR,
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
            actions=FileMember.EDITOR,
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
            file_id=uuid.uuid4(),
            actions=FileMember.EDITOR,
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
            actions=FileMember.EDITOR,
            user=FileMember.User(
                id=uuid.uuid4(),
                username="",
            )
        )
        # WHEN
        with pytest.raises(User.NotFound):
            await file_member_repo.save(member)


class TestUpdate:
    async def test(
        self,
        file_member_repo: FileMemberRepository,
        file_member_factory: FileMemberFactory,
        file: File,
        user_b: User,
    ):
        # GIVEN
        member = await file_member_factory(file_id=file.id, user_id=user_b.id)
        member_update = FileMemberUpdate(actions=FileMember.VIEWER)
        # WHEN
        updated_member = await file_member_repo.update(member, member_update)
        # THEN
        assert updated_member != member
        assert updated_member.actions == member_update["actions"]
        assert updated_member == await _get(file.id, user_b.id)

    async def test_when_member_not_found(
        self,
        file_member_repo: FileMemberRepository,
    ):
        # GIVEN
        file_id, user_id = uuid.uuid4(), uuid.uuid4()
        member = FileMember(
            file_id=file_id,
            actions=FileMember.EDITOR,
            user=FileMember.User(
                id=user_id,
                username="admin",
            )
        )
        member_update = FileMemberUpdate(actions=FileMember.VIEWER)
        # WHEN
        with pytest.raises(FileMember.NotFound):
            await file_member_repo.update(member, member_update)
