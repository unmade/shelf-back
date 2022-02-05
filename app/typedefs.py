from __future__ import annotations

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from pathlib import PurePath
    from uuid import UUID

    from edgedb import AsyncIOClient
    from edgedb.asyncio_con import AsyncIOConnection
    from edgedb.transaction import BaseAsyncIOTransaction

DBConn = AsyncIOConnection
DBPool = AsyncIOClient
DBTransaction = BaseAsyncIOTransaction
DBConnOrPool = Union[DBConn, DBPool]
DBPoolOrTransaction = Union[DBPool, DBTransaction]
DBAnyConn = Union[DBConn, DBPool, DBTransaction]

StrOrPath = Union[str, PurePath]
StrOrUUID = Union[str, UUID]
