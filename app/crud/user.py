from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app import security
from app.entities import Account, Namespace
from app.models import Namespace as NamespaceModel
from app.models import User


def create(db_session: Session, username: str, password: str) -> User:
    """Creates, saves and returns a User."""
    user = User(username=username, password=security.make_password(password))
    db_session.add(user)
    db_session.flush()

    return user


def exists(db_session: Session, user_id: int) -> bool:
    """Returns a User with a given user_id."""
    return db_session.query(
        db_session.query(User).filter(User.id == user_id).exists()
    ).scalar()


def get_by_username(db_session: Session, username: str) -> Optional[User]:
    """Returns a User with a given username."""
    return (
        db_session.query(User)
        .filter(User.username == username)
        .first()
    )


def get_account(db_session: Session, user_id: int) -> Optional[Account]:
    row = (
        db_session.query(
            User.id.label("user_id"),
            User.username.label("username"),
            NamespaceModel.id.label("namespace_id"),
            NamespaceModel.path.label("path"),
        )
        .join(NamespaceModel)
        .filter(User.id == user_id)
        .first()
    )
    if not row:
        return None
    return Account(
        id=row.user_id,
        username=row.username,
        namespace=Namespace(
            id=row.namespace_id,
            path=row.path,
            owner_id=row.user_id,
        ),
    )
