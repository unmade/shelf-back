from __future__ import annotations

import contextlib
from types import UnionType
from typing import TYPE_CHECKING, Union

import edgedb

from app import config

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.typedefs import DBClient

_client: DBClient | None = None

_TYPE_NAME = {
    "bool": "bool",
    "float": "float64",
    "int": "int64",
    "str": "str",
    "UUID": "uuid",
}


def autocast(pytype) -> str:
    """
    Cast python type to appropriate EdgeDB type.

    Args:
        pytype: Python type.

    Raises:
        TypeError: If type casting fails.

    Returns:
        str: EdgeDB type, for example: '<REQUIRED str>'.
    """
    marker = "REQUIRED"
    typename = ""

    if hasattr(pytype, "__name__"):
        typename = pytype.__name__
    if getattr(pytype, "__origin__", None) is Union or isinstance(pytype, UnionType):
        args = pytype.__args__
        if len(args) == 2 and any(isinstance(None, arg) for arg in args):
            tp = args[1] if isinstance(None, args[0]) else args[0]
            typename = tp.__name__
            marker = "OPTIONAL"

    try:
        return f"<{marker} {_TYPE_NAME[typename]}>"
    except KeyError as exc:
        raise TypeError(f"Can't cast python type `{pytype}` to EdgeDB type.") from exc


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
    ) as client:
        yield client


async def init_client() -> None:  # pragma: no cover
    """Initialize a database client."""
    global _client

    # _client = edgedb.create_async_client(
    #     dsn=config.DATABASE_DSN,
    #     max_concurrency=4,
    #     tls_ca_file=config.DATABASE_TLS_CA_FILE,
    # )


async def close_client() -> None:  # pragma: no cover
    """Gracefully close database close."""
    global _client

    assert _client is not None, "Database client is not initialized."
    await _client.aclose()
    _client = None


def client() -> DBClient:
    assert _client is not None, "Database client is not initialized."
    return _client


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
