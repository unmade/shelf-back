from __future__ import annotations

from typing import Optional, cast

from sqlalchemy.orm import Session

from app.auth import security

from .models import User


def get_by_id(db_session: Session, id: int) -> Optional[User]:
    user = db_session.query(User).filter(User.id == id).first()
    return cast(Optional[User], user)


def get_by_username(db_session: Session, username: str) -> Optional[User]:
    user = db_session.query(User).filter(User.username == username).first()
    return cast(Optional[User], user)


def create(db_session: Session, username: str, password: str) -> User:
    user = User(username=username, password=security.get_password_hash(password))
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user
