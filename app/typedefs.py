from __future__ import annotations

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from pathlib import Path
    from uuid import UUID
    from edgedb import AsyncIOConnection, AsyncIOPool, AsyncIOTransaction

DBAnyConn = Union[AsyncIOConnection, AsyncIOPool, AsyncIOTransaction]
DBConnOrPool = Union[AsyncIOConnection, AsyncIOPool]
DBPool = AsyncIOPool

StrOrPath = Union[str, Path]
StrOrUUID = Union[str, UUID]
