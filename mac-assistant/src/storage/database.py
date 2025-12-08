"""Database connection and session management."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from src.core.config import Settings, get_settings
from src.storage.models import Base

logger = logging.getLogger(__name__)


class Database:
    """Database connection manager."""

    def __init__(self, settings: Settings | None = None):
        """Initialize database.

        Args:
            settings: Application settings.
        """
        self.settings = settings or get_settings()
        self.db_path = self.settings.db_path
        self._engine = None
        self._session_factory = None
        self._initialized = False

    def _get_engine(self):
        """Get or create database engine."""
        if self._engine is None:
            # Ensure directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            db_url = f"sqlite:///{self.db_path}"
            logger.info(f"Connecting to database: {db_url}")

            self._engine = create_engine(
                db_url,
                echo=False,
                connect_args={"check_same_thread": False},
            )

            # Enable foreign keys for SQLite
            @event.listens_for(self._engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        return self._engine

    def _get_session_factory(self):
        """Get or create session factory."""
        if self._session_factory is None:
            self._session_factory = sessionmaker(
                bind=self._get_engine(),
                autocommit=False,
                autoflush=False,
            )
        return self._session_factory

    def init_db(self) -> None:
        """Initialize database schema."""
        if self._initialized:
            return

        engine = self._get_engine()
        Base.metadata.create_all(bind=engine)
        self._initialized = True
        logger.info("Database initialized")

    def get_session(self) -> Session:
        """Get a new database session."""
        self.init_db()
        return self._get_session_factory()()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Provide a transactional scope around a series of operations."""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def close(self) -> None:
        """Close database connection."""
        if self._engine:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None
            self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """Check if database is initialized."""
        return self._initialized


# Global singleton
_database: Database | None = None


def get_database() -> Database:
    """Get the global database instance."""
    global _database
    if _database is None:
        _database = Database()
    return _database


def init_database() -> Database:
    """Initialize and return the global database."""
    db = get_database()
    db.init_db()
    return db
