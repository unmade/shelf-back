from sqlalchemy import Column, ForeignKey, Integer

from app.db import Base


class Namespace(Base):
    __tablename__ = "namespaces"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
