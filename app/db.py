from __future__ import annotations

from typing import TYPE_CHECKING

import edgedb

from app import config

if TYPE_CHECKING:
    from edgedb import AsyncIOPool, AsyncIOConnection


_pool: AsyncIOPool = None


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

    await _pool.aclose()


async def db_conn() -> AsyncIOConnection:
    """Yield a new connection from a connection pool."""
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
