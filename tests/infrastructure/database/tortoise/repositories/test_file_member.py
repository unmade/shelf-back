from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.app.files.domain import FileMember
from app.infrastructure.database.tortoise.repositories.file_member import ActionFlag

if TYPE_CHECKING:
    from app.app.files.domain.file_member import FileMemberActions


class TestActionFlag:
    @pytest.mark.parametrize(["given", "expected"], [
        (FileMember.Actions(), 0),
        (FileMember.VIEWER, 3),
        (FileMember.EDITOR, 63),
        (FileMember.OWNER, -1),
    ])
    def test_dump(self, given: FileMemberActions, expected: int):
        # GIVEN
        # WHEN
        result = ActionFlag.dump(given)

        # THEN
        assert result == expected

    @pytest.mark.parametrize(["given", "expected"], [
        (0, FileMember.Actions()),
        (3, FileMember.VIEWER),
        (63, FileMember.EDITOR),
        (-1, FileMember.OWNER),
        (127, FileMember.OWNER),
    ])
    def test_load(self, given: int, expected: FileMemberActions):
        # GIVEN
        # WHEN
        result = ActionFlag.load(given)

        # THEN
        assert result == expected
