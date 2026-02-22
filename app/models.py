"""SQLAlchemy database models."""

import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.database import Base


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


class Joke(Base):
    """Chuck Norris joke stored in the database."""

    __tablename__ = "jokes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    text = Column(Text, nullable=False, unique=True)
    created_at = Column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class APIKey(Base):
    """API key for authenticating write operations."""

    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    key_hash = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
