"""
Message replay service for reprocessing failed messages.

Allows replaying individual messages or batches of failed messages.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from src.db.database import get_db_manager
from src.db.repository import MessageRepository
from src.db.models import MessageStatus
from src.config import DATABASE_MAX_RETRY_COUNT

logger = logging.getLogger(__name__)


class MessageReplayService:
    """Service for replaying failed messages."""

    def __init__(self):
        """Initialize message replay service."""
        self.max_retry_count = DATABASE_MAX_RETRY_COUNT

    async def get_failed_messages(
        self,
        limit: Optional[int] = None,
        include_maxed_retries: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get list of failed messages that can be replayed.

        Args:
            limit: Maximum number of messages to return
            include_maxed_retries: Include messages that have reached max retry count

        Returns:
            List of message dictionaries with id, raw_text, category, retry_count, error_message
        """
        db_manager = get_db_manager()
        if not db_manager or not db_manager.is_available:
            logger.error("Database not available for getting failed messages")
            return []

        try:
            async with db_manager.get_session() as session:
                max_retry = None if include_maxed_retries else self.max_retry_count
                messages = await MessageRepository.get_failed_messages(
                    session,
                    max_retry_count=max_retry,
                    limit=limit
                )

                return [
                    {
                        "id": msg.id,
                        "timestamp": msg.timestamp.isoformat(),
                        "user_id": msg.user_id,
                        "source": msg.source,
                        "category": msg.category,
                        "language": msg.language,
                        "raw_text": msg.raw_text,
                        "retry_count": msg.retry_count,
                        "error_message": msg.error_message,
                        "created_at": msg.created_at.isoformat(),
                        "updated_at": msg.updated_at.isoformat()
                    }
                    for msg in messages
                ]
        except Exception as e:
            logger.error(f"Failed to get failed messages: {e}", exc_info=True)
            return []

    async def replay_message(self, message_id: int) -> Dict[str, Any]:
        """
        Replay a specific failed message.

        Args:
            message_id: ID of message to replay

        Returns:
            Dict with success status and message info
        """
        db_manager = get_db_manager()
        if not db_manager or not db_manager.is_available:
            return {
                "success": False,
                "error": "Database not available"
            }

        try:
            async with db_manager.get_session() as session:
                # Get the message
                message = await MessageRepository.get_by_id(session, message_id)

                if not message:
                    return {
                        "success": False,
                        "error": f"Message {message_id} not found"
                    }

                if message.processing_status != MessageStatus.FAILED:
                    return {
                        "success": False,
                        "error": f"Message {message_id} is not in FAILED status (current: {message.processing_status})"
                    }

                if message.retry_count >= self.max_retry_count:
                    return {
                        "success": False,
                        "error": f"Message {message_id} has reached maximum retry count ({self.max_retry_count})"
                    }

                # Reset status to QUEUED for reprocessing
                await MessageRepository.update_status(
                    session,
                    message_id,
                    MessageStatus.QUEUED,
                    error_message=None
                )

                # Increment retry count
                await MessageRepository.increment_retry_count(session, message_id)

                logger.info(f"Message {message_id} reset to QUEUED for replay (retry {message.retry_count + 1}/{self.max_retry_count})")

                return {
                    "success": True,
                    "message_id": message_id,
                    "retry_count": message.retry_count + 1,
                    "raw_text": message.raw_text
                }

        except Exception as e:
            logger.error(f"Failed to replay message {message_id}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    async def replay_all_failed(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Replay all failed messages.

        Args:
            limit: Maximum number of messages to replay

        Returns:
            Dict with success count, failure count, and details
        """
        db_manager = get_db_manager()
        if not db_manager or not db_manager.is_available:
            return {
                "success": False,
                "error": "Database not available",
                "replayed_count": 0,
                "skipped_count": 0
            }

        replayed = []
        skipped = []

        try:
            async with db_manager.get_session() as session:
                # Get failed messages that haven't maxed out retries
                messages = await MessageRepository.get_failed_messages(
                    session,
                    max_retry_count=self.max_retry_count,
                    limit=limit
                )

                for message in messages:
                    # Reset status to QUEUED
                    success = await MessageRepository.update_status(
                        session,
                        message.id,
                        MessageStatus.QUEUED,
                        error_message=None
                    )

                    if success:
                        await MessageRepository.increment_retry_count(session, message.id)
                        replayed.append(message.id)
                        logger.info(f"Replaying message {message.id} (retry {message.retry_count + 1}/{self.max_retry_count})")
                    else:
                        skipped.append(message.id)
                        logger.warning(f"Failed to reset message {message.id} for replay")

                return {
                    "success": True,
                    "replayed_count": len(replayed),
                    "skipped_count": len(skipped),
                    "replayed_ids": replayed,
                    "skipped_ids": skipped
                }

        except Exception as e:
            logger.error(f"Failed to replay all messages: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "replayed_count": len(replayed),
                "skipped_count": len(skipped)
            }

    async def get_message_status(self, message_id: int) -> Optional[Dict[str, Any]]:
        """
        Get current status of a message.

        Args:
            message_id: ID of message

        Returns:
            Dict with message status info or None if not found
        """
        db_manager = get_db_manager()
        if not db_manager or not db_manager.is_available:
            logger.error("Database not available")
            return None

        try:
            async with db_manager.get_session() as session:
                message = await MessageRepository.get_by_id(session, message_id)

                if not message:
                    return None

                return {
                    "id": message.id,
                    "status": message.processing_status.value,
                    "retry_count": message.retry_count,
                    "error_message": message.error_message,
                    "category": message.category,
                    "language": message.language,
                    "created_at": message.created_at.isoformat(),
                    "updated_at": message.updated_at.isoformat()
                }

        except Exception as e:
            logger.error(f"Failed to get message status: {e}", exc_info=True)
            return None
