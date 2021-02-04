from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app import security
from app.entities.account import Account
from app.entities.namespace import Namespace as NamespaceEntity
from app.models import Namespace, User


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
        db_session.query(User, Namespace)
        .join(Namespace)
        .filter(User.id == user_id)
        .first()
    )
    if not result:
        return None
    user, namespace = result
    return Account(
        id=user.id,
        username=user.username,
        namespace=NamespaceEntity(
            id=namespace.id,
            path=namespace.path,
            owner_id=user.id,
        ),
    )
