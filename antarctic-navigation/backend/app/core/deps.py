"""Dependency injection utilities."""
from typing import Generator
from sqlalchemy.orm import Session
from app.core.database import get_db as _get_db
from app.core.config import get_settings as _get_settings, Settings


def get_db() -> Generator[Session, None, None]:
    """Get database session dependency."""
    yield from _get_db()


def get_settings() -> Settings:
    """Get application settings dependency."""
    return _get_settings()
