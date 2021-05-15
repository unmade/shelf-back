from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

import edgedb

from app import config

if TYPE_CHECKING:
    from app.typedefs import DBConnOrPool, DBPool

_pool: Optional[DBPool] = None

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
    typename = None

    if hasattr(pytype, "__name__"):
        typename = pytype.__name__
    if hasattr(pytype, "__origin__") and pytype.__origin__ is Union:
        args = pytype.__args__
        if len(args) == 2 and any(isinstance(None, arg) for arg in args):
            tp = args[1] if isinstance(None, args[0]) else args[0]
            typename = tp.__name__
            marker = "OPTIONAL"

    if typename is not None:
        try:
            return f"<{marker} {_TYPE_NAME[typename]}>"
        except KeyError as exc:
            raise TypeError(f"Unsupported type: `{typename}`.") from exc

    raise TypeError(f"Can't cast python type `{pytype}` to EdgeDB type.")


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
                    {schema}
                }};
                POPULATE MIGRATION;
                COMMIT MIGRATION;
            """)
