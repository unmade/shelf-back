from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.namespace import Namespace
from app.models.user import User


def create(db_session: Session, owner_id: int) -> Namespace:
    namespace = Namespace(owner_id=owner_id)
    db_session.add(namespace)
    db_session.flush()

    return namespace


def all(db_session: Session) -> List[Namespace]:
    return (
        db_session
        .query(
            Namespace.id,
            User.username.label("name"),
        )
        .join(User)
        .all()
    )


def get(db_session: Session, owner_id: int) -> Optional[Namespace]:
    return (
        db_session
        .query(Namespace.id)
        .filter(
            Namespace.owner_id == owner_id
        )
        .first()
    )
