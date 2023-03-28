from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import edgedb

from app import config

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.typedefs import DBClient


@contextlib.asynccontextmanager
async def create_client(max_concurrency: int | None = 1) -> AsyncIterator[DBClient]:
    """
    Create a new database client.

    Args:
        max_concurrency (int, optional): Max number of connections in the pool.
            Defaults to 1. Use `None` to use suggested concurrency value provided by
            the server.
    """
    async with edgedb.create_async_client(
        dsn=config.DATABASE_DSN,
        max_concurrency=max_concurrency,
        tls_ca_file=config.DATABASE_TLS_CA_FILE,
        tls_security=config.DATABASE_TLS_SECURITY,
    ) as client:
        yield client


async def migrate(conn: DBClient, schema: str) -> None:
    """
    Run migration to a target schema in a new transaction.

    Args:
        conn (DBClient): Connection to a database.
        schema (str): Schema to migrate to.
    """
    async for tx in conn.transaction():
        async with tx:
            await tx.execute(f"""
                START MIGRATION TO {{
                    {schema}
                }};
                POPULATE MIGRATION;
                COMMIT MIGRATION;
            """)
