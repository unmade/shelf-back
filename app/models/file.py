from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)

from app.db import Base


class File(Base):
    __tablename__ = "files"
    __table_args__ = (UniqueConstraint("namespace_id", "path"),)

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey(id), index=True)
    name = Column(String, nullable=False)
    path = Column(String, nullable=False)  # relative to namespace
    size = Column(Integer, nullable=False)
    mtime = Column(Float, nullable=False)
    is_dir = Column(Boolean, nullable=False)

    namespace_id = Column(Integer, ForeignKey("namespaces.id"), nullable=False)

    @property
    def type(self):
        return "folder" if self.is_dir else "file"
