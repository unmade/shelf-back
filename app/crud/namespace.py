from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.namespace import Namespace


def create(db_session: Session, path: str, owner_id: int) -> Namespace:
    namespace = Namespace(path=path, owner_id=owner_id)
    db_session.add(namespace)
    db_session.flush()

    return namespace


def all(db_session: Session) -> List[Namespace]:
    return db_session.query(Namespace.id, Namespace.path).all()


def get(db_session: Session, owner_id: int) -> Optional[Namespace]:
    return db_session.query(Namespace.id).filter(Namespace.owner_id == owner_id).first()
