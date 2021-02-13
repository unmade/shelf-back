from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from app.models import Namespace


def all(db_session: Session) -> List[Namespace]:
    return db_session.query(Namespace.id, Namespace.path).all()
