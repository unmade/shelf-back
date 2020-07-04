from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String

from app.db import Base


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(Integer, nullable=False)
    parent_id = Column(Integer, ForeignKey("files.id"), index=True)
    name = Column(String, nullable=False)
    path = Column(String, nullable=False)
    size = Column(Integer, nullable=False)
    mtime = Column(Float, nullable=False)
    is_dir = Column(Boolean, nullable=False)


class Mount(Base):
    __tablename__ = "mounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    home = Column(Boolean, nullable=False)
