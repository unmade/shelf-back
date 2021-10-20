from __future__ import annotations

import contextlib
from types import UnionType  # type: ignore
from typing import TYPE_CHECKING, Union

import edgedb

from app import config

if TYPE_CHECKING:
    from app.typedefs import DBConnOrPool, DBPool

_pool: DBPool | None = None

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
async def connect():
    """
    Acquire new connection to the database.

    Yields:
        [type]: Connection to a database.
    """
    conn = await edgedb.async_connect(
        dsn=config.DATABASE_DSN,
        tls_ca_file=config.DATABASE_TLS_CA_FILE,
    )

    try:
        yield conn
    finally:
        await conn.aclose()


async def create_pool() -> None:
    """Create a new connection pool."""
    global _pool

    _pool = await edgedb.create_async_pool(
        dsn=config.DATABASE_DSN,
        min_size=4,
        max_size=4,
        tls_ca_file=config.DATABASE_TLS_CA_FILE,
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
                    {schema}
                }};
                POPULATE MIGRATION;
                COMMIT MIGRATION;
            """)
