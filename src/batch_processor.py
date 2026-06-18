"""Batch processor for queued messages."""

import asyncio
import logging
from typing import List
import time

from src.config import (
    ANTHROPIC_API_KEY,
    PREDEFINED_CATEGORIES,
    VAULT_PATH,
    LANGUAGE_FOLDERS,
    LOGS_PATH,
    BATCH_INTERVAL_MINUTES,
    BATCH_PROCESS_LIMIT,
    GIT_AUTO_COMMIT,
    GIT_AUTO_PUSH,
    GIT_REMOTE_NAME,
    GIT_BRANCH_NAME,
    GIT_COMMIT_MESSAGE_TEMPLATE,
    YOUTUBE_ENABLED,
    validate_config
)
from src.utils.language_detector import detect_language
from src.processors.claude_processor import ClaudeProcessor
from src.processors.note_generator import ObsidianNoteGenerator
from src.utils.git_sync import GitSync
from src.utils.vault_init import init_vault_from_remote, ensure_vault_git_configured
from src.db.database import get_db_manager
from src.db.repository import MessageRepository
from src.db.models import MessageStatus

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_PATH / 'batch_processor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class BatchProcessor:
    """Processes queued messages in batches."""

    def __init__(self):
        """Initialize the batch processor."""
        # Initialize vault from remote if needed
        logger.info("Checking vault initialization...")
        if init_vault_from_remote(VAULT_PATH):
            logger.info("Vault is ready")
            ensure_vault_git_configured(VAULT_PATH)
        else:
            logger.warning("Vault initialization had issues, but continuing...")

        self.claude_processor = ClaudeProcessor(
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

        self.note_generator = ObsidianNoteGenerator(
            vault_path=VAULT_PATH,
            language_folders=LANGUAGE_FOLDERS,
            git_sync=git_sync
        )

        # Initialize YouTube processor if enabled
        self.youtube_processor = None
        if YOUTUBE_ENABLED:
            logger.info("Initializing YouTube processor for batch mode...")
            from src.processors.youtube_processor import YouTubeProcessor
            self.youtube_processor = YouTubeProcessor(self.claude_processor)
            logger.info("YouTube transcription enabled in batch processor")

        # Generate unique worker ID for this processor instance
        self.worker_id = MessageRepository._generate_worker_id()
        logger.info(f"Initialized batch processor with worker_id: {self.worker_id}")

    async def process_queue(self):
        """Process all messages in the database queue using atomic dequeue."""
        db_manager = get_db_manager()

        if not db_manager or not db_manager.is_available:
            logger.error("Database is not available - cannot process queue")
            return

        async with db_manager.get_session() as session:
            # Atomically dequeue and claim messages for this worker
            # This prevents race conditions when multiple workers are running
            claimed_messages = await MessageRepository.dequeue_atomic(
                session,
                limit=BATCH_PROCESS_LIMIT,
                worker_id=self.worker_id
            )

            if not claimed_messages:
                logger.info("No messages in queue")
                return

            # Commit immediately to persist PROCESSING status
            # This ensures messages are marked as claimed even if processing is interrupted
            await session.commit()
            logger.info(f"Worker {self.worker_id} processing {len(claimed_messages)} claimed messages...")

            success_count = 0
            fail_count = 0

            for message in claimed_messages:
                try:
                    success = await self.process_queued_message(message)
                    if success:
                        success_count += 1
                    else:
                        fail_count += 1

                except Exception as e:
                    logger.error(f"Error processing message {message.id}: {e}", exc_info=True)
                    fail_count += 1

                    # Update status to FAILED
                    async with db_manager.get_session() as update_session:
                        await MessageRepository.update_status(
                            update_session,
                            message.id,
                            MessageStatus.FAILED,
                            error_message=str(e)
                        )

            logger.info(
                f"Batch processing complete for worker {self.worker_id}. "
                f"Success: {success_count}, Failed: {fail_count}"
            )

    async def process_queued_message(self, message) -> bool:
        """
        Process a single queued message from database.

        Note: The message is already claimed with PROCESSING status by dequeue_atomic(),
        so we don't need to update status to PROCESSING here.

        Args:
            message: Message model instance from database (already in PROCESSING status)

        Returns:
            True if successful, False otherwise
        """
        db_manager = get_db_manager()

        # Track partial information for error handling
        language = None
        category_for_db = None

        try:
            message_text = message.raw_text
            logger.info(f"Processing message {message.id}: {message_text[:50]}...")

            # Detect language early (before any processing that might fail)
            try:
                language = detect_language(message_text)
                logger.info(f"Detected language: {language}")
            except Exception as e:
                logger.warning(f"Could not detect language: {e}")
                language = None

            # Track if this is a YouTube video
            is_youtube = False
            video_title = None
            video_category = None

            # Check if message contains YouTube URL and YouTube processor is enabled
            if self.youtube_processor and self.youtube_processor.is_youtube_url(message_text):
                logger.info("Detected YouTube URL in queued message")
                is_youtube = True

                # Extract URL for duplicate checking (handle category prefix)
                url_for_check = message_text
                if " -> " in message_text or " → " in message_text:
                    separator = " -> " if " -> " in message_text else " → "
                    parts = message_text.split(separator, 1)
                    if len(parts) == 2:
                        url_for_check = parts[1].strip()

                # Normalize URL for duplicate checking by extracting video ID
                try:
                    video_id = self.youtube_processor.extract_video_id(url_for_check)
                    # Construct normalized URL format (matches what's stored in DB)
                    normalized_url = f"https://www.youtube.com/watch?v={video_id}"
                except ValueError as e:
                    logger.warning(f"Could not extract video ID from URL: {e}")
                    normalized_url = url_for_check  # Fallback to original URL

                # Check for duplicate YouTube URL
                async with db_manager.get_session() as dup_session:
                    existing_message = await MessageRepository.find_completed_by_youtube_url(
                        dup_session,
                        normalized_url
                    )

                if existing_message:
                    logger.info(f"YouTube URL already processed (original message_id={existing_message.id}), marking as IGNORED")
                    async with db_manager.get_session() as session:
                        await MessageRepository.update_status(
                            session,
                            message.id,
                            MessageStatus.IGNORED,
                            error_message=f"Duplicate of message {existing_message.id}",
                            category=category_for_db,
                            language=language
                        )
                        await session.commit()
                    return False

                # Extract category if present (e.g., "History -> https://youtube.com/...")
                category = None
                url_text = message_text

                if " -> " in message_text or " → " in message_text:
                    separator = " -> " if " -> " in message_text else " → "
                    parts = message_text.split(separator, 1)
                    if len(parts) == 2:
                        category = parts[0].strip()
                        url_text = parts[1].strip()
                        # Save category early in case processing fails
                        category_for_db = category

                # Process YouTube video (returns dict with content, title, category, etc.)
                youtube_data = await self.youtube_processor.process_youtube_url(
                    url_text,
                    category=category
                )

                # Use processed transcript content as the message
                message_text = youtube_data["content"]
                video_title = youtube_data.get("title")
                video_category = youtube_data.get("category")
                video_url = youtube_data.get("url")

                # Update category for DB with video category
                if video_category:
                    category_for_db = video_category

                # Re-detect language from transcript (more accurate)
                try:
                    language = detect_language(message_text)
                    logger.info(f"Re-detected language from transcript: {language}")
                except Exception as e:
                    logger.warning(f"Could not re-detect language: {e}")

            # Process with Claude (with explicit title and category if from YouTube)
            if is_youtube:
                processed_data = self.claude_processor.process_message(
                    message_text,
                    language,
                    specified_title=video_title,
                    specified_category=video_category
                )
                # Add YouTube URL to processed data
                if video_url:
                    processed_data["url"] = video_url
            else:
                processed_data = self.claude_processor.process_message(
                    message_text,
                    language
                )

            # Add source information (normalize http_api to http)
            source = message.source if message.source else "telegram"
            if source == "http_api":
                source = "http"
            processed_data["source"] = source

            # Generate note
            note_path = self.note_generator.generate_note(processed_data, message.id)
            logger.info(f"Created note: {note_path}")

            # Update category_for_db with final category from processed_data
            if not category_for_db:
                category_for_db = processed_data.get("category")

            # Update status to COMPLETED
            async with db_manager.get_session() as session:
                await MessageRepository.update_status(
                    session,
                    message.id,
                    MessageStatus.COMPLETED,
                    category=category_for_db,
                    language=language
                )

            return True

        except Exception as e:
            logger.error(f"Failed to process message {message.id}: {e}", exc_info=True)

            # Update status to FAILED, preserving whatever information we gathered
            async with db_manager.get_session() as session:
                await MessageRepository.update_status(
                    session,
                    message.id,
                    MessageStatus.FAILED,
                    error_message=str(e),
                    category=category_for_db,  # May be None if failure was very early
                    language=language  # May be None if language detection failed
                )

            return False

    async def run_continuous(self, interval_minutes: int = None):
        """
        Run the batch processor continuously.

        Args:
            interval_minutes: Minutes between batch runs (default from config)
        """
        interval = interval_minutes or BATCH_INTERVAL_MINUTES
        logger.info(f"Starting continuous batch processor (interval: {interval} minutes)")

        try:
            while True:
                try:
                    await self.process_queue()
                except Exception as e:
                    logger.error(f"Error in batch processing cycle: {e}", exc_info=True)

                # Wait for next cycle
                logger.info(f"Waiting {interval} minutes until next batch...")
                await asyncio.sleep(interval * 60)
        except asyncio.CancelledError:
            logger.info("Batch processor shutting down gracefully...")
            raise


async def main():
    """Main entry point for batch processor."""
    try:
        # Validate configuration
        validate_config()

        # Initialize database
        from src.utils.db_init import initialize_database
        logger.info("Initializing database...")
        db_available = await initialize_database()
        if not db_available:
            logger.error("Database initialization failed - cannot run batch processor")
            return

        logger.info("Database initialized successfully")

        # Create processor
        processor = BatchProcessor()

        # Check for command line argument
        import sys
        if len(sys.argv) > 1 and sys.argv[1] == "--once":
            # Process once and exit
            logger.info("Running batch processor once")
            await processor.process_queue()
        else:
            # Run continuously
            await processor.run_continuous()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal (Ctrl+C)")
    except asyncio.CancelledError:
        logger.info("Batch processor cancelled")
    finally:
        logger.info("Batch processor stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Suppress the KeyboardInterrupt traceback
        pass
