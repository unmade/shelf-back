from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Dict

import edgedb
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app import config

if TYPE_CHECKING:
    from edgedb import AsyncIOPool, AsyncIOConnection


def get_db_params(dsn: str) -> Dict[str, Any]:
    if dsn.startswith("sqlite"):
        return {
            "connect_args": {
                "check_same_thread": False,
            },
            "poolclass": NullPool,
        }
    return {}


engine = create_engine(config.DATABASE_DSN, **get_db_params(config.DATABASE_DSN))

Base = declarative_base()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session():
    try:
        session = SessionLocal()
        yield session
    finally:
        session.close()


SessionManager = contextmanager(get_session)


def ping_db():
    with SessionManager() as db_session:
        db_session.execute("SELECT 1", bind=engine)


_pool: AsyncIOPool = None


async def create_pool() -> None:
    """Create a new connection pool."""
    global _pool

    _pool = await edgedb.create_async_pool(dsn=config.EDGEDB_DSN)


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
