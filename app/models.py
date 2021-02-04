from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db import Base


class File(Base):
    __tablename__ = "files"
    __table_args__ = (
        UniqueConstraint("namespace_id", "path"),
    )

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey(id, ondelete="CASCADE"), index=True)
    name = Column(String, nullable=False)
    path = Column(String, nullable=False)  # relative to namespace
    size = Column(Integer, nullable=False)
    mtime = Column(Float, nullable=False)
    is_dir = Column(Boolean, nullable=False)

    namespace_id = Column(Integer, ForeignKey("namespaces.id"), nullable=False)

    @property
    def type(self):
        return "folder" if self.is_dir else "file"


class Namespace(Base):
    __tablename__ = "namespaces"

    id = Column(Integer, primary_key=True, index=True)
    path = Column(String, unique=True, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    owner = relationship("User", back_populates="namespaces")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(32), unique=True, index=True, nullable=False)
    password = Column(String(64), nullable=False)

    namespaces = relationship("Namespace", back_populates="owner")
