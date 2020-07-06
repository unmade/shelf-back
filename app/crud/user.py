from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app import security
from app.entities.account import Account
from app.models.namespace import Namespace
from app.models.user import User


def create(db_session: Session, username: str, password: str) -> User:
    user = User(username=username, password=security.get_password_hash(password))
    db_session.add(user)
    db_session.flush()

    return user


def get(
    db_session: Session, user_id: int = None, username: str = None,
) -> Optional[User]:
    query = db_session.query(User)
    if user_id is not None:
        query = query.filter(User.id == user_id)
    if username is not None:
        query = query.filter(User.username == username)
    return query.first()


def get_account(db_session: Session, user_id: int) -> Optional[Account]:
    result = (
        db_session.query(User.id, User.username, Namespace.id.label("namespace_id"))
        .join(Namespace)
        .first()
    )
    if not result:
        return None
    return Account(
        id=result.id, username=result.username, namespace_id=result.namespace_id,
    )
