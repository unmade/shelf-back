from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from uuid import UUID


StrOrUUID: TypeAlias = str | UUID
