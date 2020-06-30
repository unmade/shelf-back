from contextlib import contextmanager
from typing import Any, Dict

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config


def get_db_params(dsn: str) -> Dict[str, Any]:
    if dsn.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
    return {}


engine = create_engine(config.DATABASE_DSN, **get_db_params(config.DATABASE_DSN))

Base = declarative_base()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, binds={Base: engine})


@contextmanager
def SessionManager():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def ping_db():
    with SessionManager() as db_session:
        db_session.execute("SELECT 1", bind=engine)
