from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from app.app.files.domain import FileMember

if TYPE_CHECKING:
    from app.app.files.domain.file_member import FileMemberActions

__all__ = ["ActionFlag"]


class ActionFlag(enum.IntFlag):
    # new values should be added strictly to the end
    can_view = enum.auto()
    can_download = enum.auto()
    can_upload = enum.auto()
    can_move = enum.auto()
    can_delete = enum.auto()
    can_reshare = enum.auto()
    can_unshare = enum.auto()

    @classmethod
    def dump(cls, value: FileMemberActions) -> int:
        flag = cls(0)
        if value.can_view:
            flag |= cls.can_view
        if value.can_download:
            flag |= cls.can_download
        if value.can_upload:
            flag |= cls.can_upload
        if value.can_move:
            flag |= cls.can_move
        if value.can_delete:
            flag |= cls.can_delete
        if value.can_reshare:
            flag |= cls.can_reshare
        if value.can_unshare:
            flag |= cls.can_unshare

        if flag == cls(-1):
            return -1
        return flag.value

    @classmethod
    def load(cls, value: int) -> FileMemberActions:
        if value == -1:
            return FileMember.OWNER

        return FileMember.Actions(
            can_view=bool(cls.can_view & value),
            can_download=bool(cls.can_download & value),
            can_upload=bool(cls.can_upload & value),
            can_move=bool(cls.can_move & value),
            can_delete=bool(cls.can_delete & value),
            can_reshare=bool(cls.can_reshare & value),
            can_unshare=bool(cls.can_unshare & value),
        )
