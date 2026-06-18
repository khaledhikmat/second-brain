"""
Database connection manager with graceful degradation.

Supports both SQLite (development) and PostgreSQL (production).
If database is unavailable, logs errors but allows the system to continue operating.
"""

import logging
from typing import Optional
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool, StaticPool
from sqlalchemy import text

from src.db.models import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages database connections with graceful degradation.

    Features:
    - Async SQLAlchemy engine for non-blocking operations
    - Connection pooling optimized for async workloads
    - Graceful degradation: logs errors but doesn't crash the app
    - Support for both SQLite and PostgreSQL
    """

    def __init__(self, database_url: str, echo: bool = False):
        """
        Initialize database manager.

        Args:
            database_url: Database connection URL
                - SQLite: "sqlite+aiosqlite:///./notes.db"
                - PostgreSQL: "postgresql+asyncpg://user:pass@host/db"
            echo: Whether to log SQL queries (useful for debugging)
        """
        self.database_url = database_url
        self.echo = echo
        self.engine = None
        self.session_factory = None
        self._is_available = False

    async def initialize(self) -> bool:
        """
        Initialize database connection and create tables.

        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            # Configure engine based on database type
            if "sqlite" in self.database_url:
                # SQLite specific settings
                self.engine = create_async_engine(
                    self.database_url,
                    echo=self.echo,
                    # Use StaticPool for SQLite to avoid threading issues
                    poolclass=StaticPool,
                    # SQLite-specific connection args
                    connect_args={"check_same_thread": False}
                )
            else:
                # PostgreSQL settings
                self.engine = create_async_engine(
                    self.database_url,
                    echo=self.echo,
                    pool_size=5,
                    max_overflow=10,
                    pool_pre_ping=True,  # Verify connections before using
                )

            # Create session factory
            self.session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )

            # Create tables if they don't exist
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            # Mark as available before testing connection
            self._is_available = True

            # Test connection
            async with self.get_session() as session:
                await session.execute(text("SELECT 1"))

            logger.info(f"Database initialized successfully: {self._mask_url(self.database_url)}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}", exc_info=True)
            self._is_available = False
            return False

    @asynccontextmanager
    async def get_session(self):
        """
        Get a database session with automatic cleanup.

        Usage:
            async with db_manager.get_session() as session:
                # Use session here
                pass

        Yields:
            AsyncSession: Database session
        """
        if not self._is_available or not self.session_factory:
            raise RuntimeError("Database is not available")

        session = self.session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    @asynccontextmanager
    async def get_session_safe(self):
        """
        Get a database session with graceful degradation.

        If database is unavailable, yields None instead of raising an error.
        Use this for non-critical operations where the system should continue
        even if database writes fail.

        Usage:
            async with db_manager.get_session_safe() as session:
                if session:
                    # Use session here
                    pass
                else:
                    # Database unavailable, handle gracefully
                    logger.warning("Database unavailable, skipping operation")

        Yields:
            Optional[AsyncSession]: Database session or None if unavailable
        """
        if not self._is_available or not self.session_factory:
            logger.warning("Database unavailable, operating in degraded mode")
            yield None
            return

        session = self.session_factory()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database operation failed: {e}", exc_info=True)
            # Don't re-raise - allow system to continue
        finally:
            await session.close()

    async def close(self):
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connections closed")

    @property
    def is_available(self) -> bool:
        """Check if database is available."""
        return self._is_available

    async def health_check(self) -> bool:
        """
        Perform health check on database connection.

        Returns:
            bool: True if database is healthy, False otherwise
        """
        if not self._is_available:
            return False

        try:
            async with self.get_session() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            self._is_available = False
            return False

    def _mask_url(self, url: str) -> str:
        """Mask sensitive information in database URL for logging."""
        if "@" in url:
            # Mask password in PostgreSQL URLs
            parts = url.split("@")
            credentials = parts[0].split("://")
            if len(credentials) > 1 and ":" in credentials[1]:
                user = credentials[1].split(":")[0]
                masked = f"{credentials[0]}://{user}:****@{parts[1]}"
                return masked
        return url


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> Optional[DatabaseManager]:
    """Get the global database manager instance."""
    return _db_manager


def set_db_manager(manager: DatabaseManager):
    """Set the global database manager instance."""
    global _db_manager
    _db_manager = manager
