from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import edgedb

from app import config

if TYPE_CHECKING:
    from app.typedefs import DBConnOrPool, DBPool


_pool: Optional[DBPool] = None


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
    _pool = None


def db_pool() -> DBPool:
    assert _pool is not None, "Connection pool is not initialized."
    return _pool


async def migrate(conn: DBConnOrPool, schema: str) -> None:
    """
    Run migration to a target schema in a new transaction.

    Args:
        conn (DBConnOrPool): Connection to a database.
        schema (str): Schema to migrate to.
    """
    async for tx in conn.retrying_transaction():
        async with tx:
            await tx.execute(f"""
                START MIGRATION TO {{
                    module default {{
                        {schema}
                    }}
                }};
                POPULATE MIGRATION;
                COMMIT MIGRATION;
            """)
