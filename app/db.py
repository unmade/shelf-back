from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, AsyncGenerator, Optional

import edgedb

from app import config

if TYPE_CHECKING:
    from edgedb import AsyncIOPool, AsyncIOConnection, AsyncIOTransaction


_pool: Optional[AsyncIOPool] = None


async def create_pool() -> None:
    """Create a new connection pool."""
    global _pool

    _pool = await edgedb.create_async_pool(
        dsn=config.EDGEDB_DSN,
        min_size=4,
        max_size=4,
    )


async def close_pool() -> None:
    """Gracefully close connection pool."""
    global _pool

    assert _pool is not None, "Connection pool is not initialized."
    await _pool.aclose()


async def db_conn() -> AsyncGenerator[AsyncIOConnection, None]:
    """Yield a new connection from a connection pool."""
    global _pool

    assert _pool is not None, "Connection pool is not initialized."
    async with _pool.acquire() as conn:
        yield conn


async def migrate(conn: AsyncIOConnection, schema: str) -> None:
    """
    Run migration to a target schema in a new transaction.

    Args:
        conn (AsyncIOConnection): Connection to a database.
        schema (str): Schema to migrate to.
    """
    async with conn.transaction():
        await conn.execute(f"""
            START MIGRATION TO {{
                module default {{
                    {schema}
                }}
            }};
            POPULATE MIGRATION;
            COMMIT MIGRATION;
        """)


class _TryTransaction:
    __slots__ = ("conn", "transaction", "success")

    def __init__(self, conn: AsyncIOConnection):
        self.conn = conn
        self.success = False
        self.transaction: Optional[AsyncIOTransaction] = None

    async def __aenter__(self) -> None:
        self.transaction = self.conn.transaction()
        await self.transaction.start()
        return None

    async def __aexit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            await self.transaction.rollback()
            if isinstance(exc_value, edgedb.TransactionSerializationError):
                return True
        else:
            await self.transaction.commit()
            self.success = True


# see discussion: https://github.com/edgedb/edgedb/discussions/1738
async def retry(
    conn: AsyncIOConnection, *, wait: float = 0.1, max_attempts: int = 3,
) -> AsyncGenerator[_TryTransaction, None]:
    """
    Start a new transaction, if it fails with `edgedb.TransactionSerializationError`,
    wait for `wait` seconds and start a new one.

    Args:
        conn (AsyncIOConnection): Database connection.
        wait (float, optional): How many seconds to wait before yield next transaction.
            Defaults to 0.1s.
        max_attempts (int, optional): How many times to try. Defaults to 3.
    """
    for _ in range(max_attempts):
        tx = _TryTransaction(conn)
        yield tx
        if tx.success:
            return
        if wait:
            await asyncio.sleep(wait)
