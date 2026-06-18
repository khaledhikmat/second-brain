"""Main application entry point."""

import asyncio
import logging
from pathlib import Path

from src.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_ALLOWED_USER_ID,
    ANTHROPIC_API_KEY,
    PREDEFINED_CATEGORIES,
    VAULT_PATH,
    LANGUAGE_FOLDERS,
    BATCH_MODE,
    QUEUE_PATH,
    LOGS_PATH,
    GIT_AUTO_COMMIT,
    GIT_AUTO_PUSH,
    GIT_REMOTE_NAME,
    GIT_BRANCH_NAME,
    GIT_COMMIT_MESSAGE_TEMPLATE,
    HTTP_API_ENABLED,
    HTTP_API_KEY,
    WEBHOOK_HOST,
    WEBHOOK_PORT,
    YOUTUBE_ENABLED,
    validate_config
)
from src.handlers.telegram_handler import TelegramHandler
from src.processors.claude_processor import ClaudeProcessor
from src.processors.note_generator import ObsidianNoteGenerator
from src.utils.git_sync import GitSync
from src.utils.vault_init import init_vault_from_remote, ensure_vault_git_configured
from src.utils.db_init import initialize_database, close_database

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_PATH / 'app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def main():
    """Main application entry point."""
    try:
        # Validate configuration
        logger.info("Validating configuration...")
        validate_config()
        logger.info("Configuration validated successfully")

        # Initialize database
        logger.info("Initializing database...")
        db_available = await initialize_database()
        if db_available:
            logger.info("Database initialized and ready")
        else:
            logger.warning("Database unavailable - operating in degraded mode (file-only storage)")

        # Initialize vault from remote if needed (for cloud deployments)
        logger.info("Checking vault initialization...")
        if init_vault_from_remote(VAULT_PATH):
            logger.info("Vault is ready")
            # Ensure Git is configured if it's a git repo
            ensure_vault_git_configured(VAULT_PATH)
        else:
            logger.warning("Vault initialization had issues, but continuing...")

        # Initialize processors
        logger.info("Initializing Claude processor...")
        claude_processor = ClaudeProcessor(
            api_key=ANTHROPIC_API_KEY,
            predefined_categories=PREDEFINED_CATEGORIES
        )

        # Initialize Git sync if enabled
        git_sync = None
        if GIT_AUTO_COMMIT:
            logger.info("Initializing Git sync...")
            git_sync = GitSync(
                vault_path=VAULT_PATH,
                auto_commit=GIT_AUTO_COMMIT,
                auto_push=GIT_AUTO_PUSH,
                remote_name=GIT_REMOTE_NAME,
                branch_name=GIT_BRANCH_NAME,
                commit_message_template=GIT_COMMIT_MESSAGE_TEMPLATE
            )
            logger.info(f"Git sync enabled (auto_push: {GIT_AUTO_PUSH})")
        else:
            logger.info("Git sync is disabled")

        logger.info("Initializing note generator...")
        note_generator = ObsidianNoteGenerator(
            vault_path=VAULT_PATH,
            language_folders=LANGUAGE_FOLDERS,
            git_sync=git_sync
        )

        # Initialize YouTube processor if enabled
        youtube_processor = None
        if YOUTUBE_ENABLED:
            logger.info("Initializing YouTube processor...")
            from src.processors.youtube_processor import YouTubeProcessor
            youtube_processor = YouTubeProcessor(claude_processor)
            logger.info("YouTube transcription enabled")

        # Initialize Telegram handler
        logger.info("Initializing Telegram handler...")
        telegram_handler = TelegramHandler(
            bot_token=TELEGRAM_BOT_TOKEN,
            allowed_user_id=TELEGRAM_ALLOWED_USER_ID,
            claude_processor=claude_processor,
            note_generator=note_generator,
            batch_mode=BATCH_MODE,
            queue_path=QUEUE_PATH if BATCH_MODE else None,
            youtube_processor=youtube_processor
        )

        # Initialize HTTP API handler if enabled
        http_handler = None
        if HTTP_API_ENABLED:
            logger.info("Initializing HTTP API handler...")
            from src.handlers.http_handler import HTTPHandler
            http_handler = HTTPHandler(
                claude_processor=claude_processor,
                note_generator=note_generator,
                api_key=HTTP_API_KEY,
                youtube_processor=youtube_processor,
                batch_mode=BATCH_MODE
            )
            logger.info(f"HTTP API enabled on {WEBHOOK_HOST}:{WEBHOOK_PORT} (batch_mode={BATCH_MODE})")

        # Start the services
        mode = "BATCH" if BATCH_MODE else "IMMEDIATE"
        logger.info(f"Starting Notes Processor in {mode} mode...")
        logger.info(f"Vault path: {VAULT_PATH}")
        logger.info(f"Allowed user ID: {TELEGRAM_ALLOWED_USER_ID}")

        # Collect tasks to run
        tasks = [telegram_handler.start_polling()]

        if http_handler:
            tasks.append(http_handler.start(WEBHOOK_HOST, WEBHOOK_PORT))

        # Run all handlers concurrently
        if len(tasks) > 1:
            logger.info(f"Running {len(tasks)} handlers concurrently...")
            await asyncio.gather(*tasks)
        else:
            await tasks[0]

    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise
    finally:
        # Cleanup database connections
        logger.info("Closing database connections...")
        await close_database()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Suppress the KeyboardInterrupt traceback
        pass
