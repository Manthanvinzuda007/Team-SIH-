"""Database configuration and session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


_engine = None
_SessionLocal = None


def _ensure_initialized():
    """Lazy-initialize the database engine and session factory."""
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        connect_args = {}
        if settings.DATABASE_URL.startswith("sqlite"):
            connect_args = {"check_same_thread": False}

        _engine = create_engine(
            settings.DATABASE_URL,
            connect_args=connect_args,
            echo=False,
        )
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def get_engine():
    _ensure_initialized()
    return _engine


def SessionLocal():
    """Get a new database session (lazy-initializes if needed)."""
    _ensure_initialized()
    return _SessionLocal()


def init_db():
    """Initialize database engine and session factory."""
    _ensure_initialized()
    return _engine


def get_db():
    """Dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all database tables."""
    _ensure_initialized()
    Base.metadata.create_all(bind=_engine)
