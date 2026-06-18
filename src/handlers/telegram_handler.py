"""Telegram message handler."""

import logging
from typing import Optional
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
import json
from pathlib import Path
from datetime import datetime

from src.utils.language_detector import detect_language
from src.processors.claude_processor import ClaudeProcessor
from src.processors.note_generator import ObsidianNoteGenerator
from src.db.database import get_db_manager
from src.db.repository import MessageRepository
from src.db.models import MessageStatus

logger = logging.getLogger(__name__)


class TelegramHandler:
    """Handles incoming Telegram messages and processes them into notes."""

    def __init__(
        self,
        bot_token: str,
        allowed_user_id: str,
        claude_processor: ClaudeProcessor,
        note_generator: ObsidianNoteGenerator,
        batch_mode: bool = False,
        queue_path: Optional[Path] = None,
        youtube_processor: Optional['YouTubeProcessor'] = None
    ):
        """
        Initialize the Telegram handler.

        Args:
            bot_token: Telegram bot token
            allowed_user_id: Allowed Telegram user ID (for security)
            claude_processor: Claude processor instance
            note_generator: Note generator instance
            batch_mode: Whether to use batch processing
            queue_path: Path to queue directory (required if batch_mode=True)
            youtube_processor: Optional YouTube processor instance
        """
        self.bot_token = bot_token
        self.allowed_user_id = str(allowed_user_id)
        self.claude_processor = claude_processor
        self.note_generator = note_generator
        self.batch_mode = batch_mode
        self.queue_path = queue_path
        self.youtube_processor = youtube_processor

        if batch_mode and not queue_path:
            raise ValueError("queue_path is required when batch_mode is enabled")

        self.application = None

    async def start_polling(self):
        """Start the Telegram bot with polling."""
        self.application = ApplicationBuilder().token(self.bot_token).build()

        # Add message handler
        message_handler = MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handle_message
        )
        self.application.add_handler(message_handler)

        # Start polling
        logger.info("Starting Telegram bot polling...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

        # Keep running indefinitely (will be stopped by Ctrl+C or signal)
        # The application will handle shutdown signals automatically
        import asyncio
        try:
            # Run forever - polling happens in background
            await asyncio.Event().wait()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Received shutdown signal")
        finally:
            # Cleanup
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle incoming Telegram messages.

        Args:
            update: Telegram update object
            context: Telegram context
        """
        try:
            # Security check: only process messages from allowed user
            user_id = str(update.effective_user.id)
            if user_id != self.allowed_user_id:
                logger.warning(f"Rejected message from unauthorized user: {user_id}")
                await update.message.reply_text(
                    "Sorry, you are not authorized to use this bot."
                )
                return

            message_text = update.message.text

            if not message_text or not message_text.strip():
                await update.message.reply_text("Received empty message.")
                return

            logger.info(f"Received message from authorized user: {user_id}")

            if self.batch_mode:
                # Queue the message for batch processing
                # YouTube URLs will be processed later by the batch processor
                await self._queue_message(message_text, update)

                # Check if it's a YouTube URL to give appropriate feedback
                if self.youtube_processor and self.youtube_processor.is_youtube_url(message_text):
                    await update.message.reply_text(
                        "✓ YouTube URL queued for batch processing.\n"
                        "Video will be transcribed and processed in the next batch run."
                    )
                else:
                    await update.message.reply_text(
                        "✓ Message queued for batch processing."
                    )
            else:
                # Process immediately
                await update.message.reply_text("Processing your message...")

                # Store message in database
                message_id = await self._store_message(message_text, user_id)

                note_path = await self._process_message(message_text, message_id)

                if note_path:
                    await update.message.reply_text(
                        f"✓ Note created successfully!\n\nLocation: {note_path.relative_to(note_path.parents[2])}"
                    )
                else:
                    await update.message.reply_text(
                        "✗ Failed to create note. Check logs for details."
                    )

        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            await update.message.reply_text(
                "An error occurred while processing your message."
            )

    async def _store_message(self, message_text: str, user_id: str) -> Optional[int]:
        """
        Store message in database.

        Args:
            message_text: The message content
            user_id: Telegram user ID

        Returns:
            Message ID or None if database unavailable
        """
        db_manager = get_db_manager()
        if not db_manager or not db_manager.is_available:
            logger.warning("Database unavailable, skipping message storage")
            return None

        try:
            async with db_manager.get_session_safe() as session:
                if session:
                    message = await MessageRepository.create(
                        session,
                        raw_text=message_text,
                        source="telegram",
                        user_id=user_id
                    )
                    if message:
                        logger.info(f"Stored message in database: id={message.id}")
                        return message.id
                    return None
                return None
        except Exception as e:
            logger.error(f"Failed to store message: {e}", exc_info=True)
            return None

    async def _process_message(self, message_text: str, message_id: Optional[int] = None) -> Optional[Path]:
        """
        Process a single message into a note.

        Args:
            message_text: The message content
            message_id: Optional database message ID

        Returns:
            Path to created note, or None if failed
        """
        db_manager = get_db_manager()

        try:
            # Update status to PROCESSING
            if message_id and db_manager and db_manager.is_available:
                async with db_manager.get_session_safe() as session:
                    if session:
                        await MessageRepository.update_status(
                            session,
                            message_id,
                            MessageStatus.PROCESSING
                        )

            # Check if message contains YouTube URL and YouTube processor is enabled
            is_youtube = False
            video_title = None
            video_category = None
            video_url = None

            if self.youtube_processor and self.youtube_processor.is_youtube_url(message_text):
                logger.info("Detected YouTube URL in message")
                is_youtube = True

                # Extract category if present (e.g., "History -> https://youtube.com/...")
                category = None
                url_text = message_text

                if " -> " in message_text or " → " in message_text:
                    separator = " -> " if " -> " in message_text else " → "
                    parts = message_text.split(separator, 1)
                    if len(parts) == 2:
                        category = parts[0].strip()
                        url_text = parts[1].strip()

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

            # Detect language
            language = detect_language(message_text)
            logger.info(f"Detected language: {language}")

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

            # Add source information
            processed_data["source"] = "telegram"

            # Generate note (this will also update the database with note metadata)
            note_path = self.note_generator.generate_note(processed_data, message_id)

            # Update status to COMPLETED
            if message_id and db_manager and db_manager.is_available:
                async with db_manager.get_session_safe() as session:
                    if session:
                        await MessageRepository.update_status(
                            session,
                            message_id,
                            MessageStatus.COMPLETED,
                            category=processed_data.get("category"),
                            language=language
                        )

            return note_path

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)

            # Update status to FAILED
            if message_id and db_manager and db_manager.is_available:
                async with db_manager.get_session_safe() as session:
                    if session:
                        await MessageRepository.update_status(
                            session,
                            message_id,
                            MessageStatus.FAILED,
                            error_message=str(e)
                        )

            return None

    async def _queue_message(self, message_text: str, update: Update):
        """
        Queue a message for batch processing in database.

        Args:
            message_text: The message content
            update: Telegram update object
        """
        user_id = str(update.effective_user.id)
        telegram_message_id = str(update.message.message_id)

        # Extract category if present (e.g., "Poetry -> content")
        category = None
        if " -> " in message_text or " → " in message_text:
            separator = " -> " if " -> " in message_text else " → "
            parts = message_text.split(separator, 1)
            if len(parts) == 2:
                # Check if first part looks like a category (single word or short phrase)
                potential_category = parts[0].strip()
                if len(potential_category) < 50 and not potential_category.startswith("http"):
                    category = potential_category
                    logger.debug(f"Extracted category from message: {category}")

        # Store in database with QUEUED status
        db_manager = get_db_manager()
        if db_manager and db_manager.is_available:
            try:
                async with db_manager.get_session_safe() as session:
                    if session:
                        await MessageRepository.create(
                            session,
                            raw_text=message_text,
                            source="telegram",
                            user_id=user_id,
                            source_message_id=telegram_message_id,
                            category=category,
                            processing_status=MessageStatus.QUEUED
                        )
                        logger.info(f"Queued message in database for user {user_id} (category: {category or 'none'})")
            except Exception as e:
                logger.error(f"Failed to queue message in database: {e}", exc_info=True)
                raise RuntimeError("Failed to queue message - database unavailable")
        else:
            logger.error("Database is not available - cannot queue message")
            raise RuntimeError("Database is required for batch mode but is unavailable")
