from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from pathlib import PurePath
    from uuid import UUID


StrOrPath: TypeAlias = str | PurePath
StrOrUUID: TypeAlias = str | UUID
