"""
Main application entry point.
"""

import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv

from services.setting.envars import EnvVarsSettingService
from services.logger.dual import DualLoggerService
from services.data.postgres import PostgresDataService
from services.data.typex import MessageStatus
from services.storage.r2 import R2StorageService
from channels.http.handler import HttpHandler
from channels.telegram.handler import TelegramHandler

# Load environment variables
load_dotenv()

async def main():
    """Main application entry point."""
    db_service = None

    settings_service = EnvVarsSettingService()
    logger_service = DualLoggerService(settings_service)
    logger_service.info(f"Starting main processor")

    try:
        # Initialize database service
        logger_service.info("Connecting to database...")
        db_service = PostgresDataService(settings_service, logger_service)
        await db_service.initialize()

        # Initialize Telegram handler
        logger_service.info("Initializing Telegram handler...")
        telegram_handler = TelegramHandler(settings_service, logger_service, db_service)

        # Initialize HTTP handler
        logger_service.info("Initializing HTTP API handler...")
        r2_service = R2StorageService(settings_service, logger_service)
        http_handler = HttpHandler(settings_service, logger_service, db_service, telegram_handler, storage_service=r2_service)

        # Start HTTP server (blocks until server stops)
        await http_handler.start()

    except KeyboardInterrupt:
        logger_service.info("Shutting down gracefully...")
    except Exception as e:
        logger_service.error(f"Fatal error: {e}")
        raise
    finally:
        # Cleanup - shield from cancellation
        logger_service.info("Shutting down services...")
        try:
            if 'http_handler' in locals():
                await asyncio.shield(http_handler.stop())
        except asyncio.CancelledError:
            logger_service.debug("HTTP handler cleanup cancelled")
        except Exception as e:
            logger_service.error(f"Error stopping HTTP handler: {e}")

        try:
            if db_service:
                logger_service.info("Disconnecting from database...")
                await asyncio.shield(db_service.finalize())
        except asyncio.CancelledError:
            logger_service.debug("Database cleanup cancelled")
        except Exception as e:
            logger_service.error(f"Error closing database: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Suppress the KeyboardInterrupt traceback
        pass
