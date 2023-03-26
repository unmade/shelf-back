from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from pathlib import PurePath
    from uuid import UUID

    from edgedb.asyncio_client import AsyncIOClient

DBClient: TypeAlias = AsyncIOClient

StrOrPath: TypeAlias = str | PurePath
StrOrUUID: TypeAlias = str | UUID
