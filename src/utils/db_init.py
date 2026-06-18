"""
Database initialization utility.

Sets up the database connection on application startup.
"""

import logging
from src.db.database import DatabaseManager, set_db_manager
from src.config import DATABASE_ENABLED, DATABASE_URL, DATABASE_ECHO

logger = logging.getLogger(__name__)


async def initialize_database() -> bool:
    """
    Initialize database connection on application startup.

    Returns:
        bool: True if database is available, False if operating in degraded mode
    """
    if not DATABASE_ENABLED:
        logger.info("Database is disabled in configuration")
        return False

    logger.info("Initializing database...")

    try:
        # Create database manager
        db_manager = DatabaseManager(
            database_url=DATABASE_URL,
            echo=DATABASE_ECHO
        )

        # Initialize connection and create tables
        success = await db_manager.initialize()

        if success:
            # Set global database manager
            set_db_manager(db_manager)
            logger.info("Database initialized successfully")
            return True
        else:
            logger.warning("Database initialization failed, operating in degraded mode")
            return False

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        logger.warning("Continuing without database (degraded mode)")
        return False


async def close_database():
    """Close database connections on application shutdown."""
    from src.db.database import get_db_manager

    db_manager = get_db_manager()
    if db_manager:
        await db_manager.close()
        logger.info("Database connections closed")
