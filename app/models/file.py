from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String

from app.db import Base


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("files.id"), index=True)
    name = Column(String, nullable=False)
    path = Column(String, nullable=False)
    size = Column(Integer, nullable=False)
    mtime = Column(Float, nullable=False)
    is_dir = Column(Boolean, nullable=False)

    namespace_id = Column(Integer, ForeignKey("namespaces.id"), nullable=False)

    # namespace_id and path should be unique_together
    # path is relative to namespace

    @property
    def type(self):
        return "folder" if self.is_dir else "file"
