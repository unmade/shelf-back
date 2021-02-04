from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(32), unique=True, index=True, nullable=False)
    password = Column(String(64), nullable=False)

    namespaces = relationship("Namespace", back_populates="owner")
