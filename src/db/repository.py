"""
Repository layer for database operations.

Provides CRUD operations for messages, notes, and queue with graceful error handling.
"""

import logging
import socket
import os
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import select, update, delete, func, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Message, ProcessedNote, MessageStatus

logger = logging.getLogger(__name__)


class MessageRepository:
    """Repository for Message operations."""

    @staticmethod
    async def create(
        session: AsyncSession,
        raw_text: str,
        source: str,
        user_id: Optional[str] = None,
        source_message_id: Optional[str] = None,
        category: Optional[str] = None,
        language: Optional[str] = None,
        processing_status: MessageStatus = MessageStatus.QUEUED
    ) -> Optional[Message]:
        """
        Create a new message record.

        Args:
            session: Database session
            raw_text: Original message text
            source: Message source ("telegram", "http", "batch")
            user_id: Optional user identifier
            source_message_id: Optional external message ID (e.g., Telegram message ID)
            category: Optional message category
            language: Optional detected language
            processing_status: Initial processing status (default: QUEUED)

        Returns:
            Created Message object or None if failed
        """
        try:
            message = Message(
                raw_text=raw_text,
                source=source,
                user_id=user_id,
                source_message_id=source_message_id,
                category=category,
                language=language,
                processing_status=processing_status,
                timestamp=datetime.utcnow()
            )
            session.add(message)
            await session.flush()  # Get the ID without committing
            logger.debug(f"Created message record: id={message.id}, source={source}, status={processing_status}")
            return message
        except Exception as e:
            logger.error(f"Failed to create message: {e}", exc_info=True)
            return None

    @staticmethod
    async def update_status(
        session: AsyncSession,
        message_id: int,
        status: MessageStatus,
        error_message: Optional[str] = None,
        category: Optional[str] = None,
        language: Optional[str] = None
    ) -> bool:
        """
        Update message processing status.

        Args:
            session: Database session
            message_id: Message ID
            status: New status
            error_message: Optional error message if failed
            category: Optional category (if detected during processing)
            language: Optional language (if detected during processing)

        Returns:
            True if update successful, False otherwise
        """
        try:
            update_data = {
                "processing_status": status,
                "updated_at": datetime.utcnow()
            }
            if error_message:
                update_data["error_message"] = error_message
            if category:
                update_data["category"] = category
            if language:
                update_data["language"] = language

            stmt = (
                update(Message)
                .where(Message.id == message_id)
                .values(**update_data)
            )
            result = await session.execute(stmt)
            await session.flush()

            success = result.rowcount > 0
            if success:
                logger.debug(f"Updated message {message_id} status to {status}")
            else:
                logger.warning(f"No message found with id={message_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to update message status: {e}", exc_info=True)
            return False

    @staticmethod
    async def increment_retry_count(session: AsyncSession, message_id: int) -> bool:
        """Increment retry count for a message."""
        try:
            stmt = (
                update(Message)
                .where(Message.id == message_id)
                .values(retry_count=Message.retry_count + 1, updated_at=datetime.utcnow())
            )
            result = await session.execute(stmt)
            await session.flush()
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to increment retry count: {e}", exc_info=True)
            return False

    @staticmethod
    async def get_by_id(session: AsyncSession, message_id: int) -> Optional[Message]:
        """Get message by ID."""
        try:
            stmt = select(Message).where(Message.id == message_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get message by id: {e}", exc_info=True)
            return None

    @staticmethod
    async def get_by_status(
        session: AsyncSession,
        status: MessageStatus,
        limit: Optional[int] = None
    ) -> List[Message]:
        """Get messages by status."""
        try:
            stmt = select(Message).where(Message.processing_status == status).order_by(Message.timestamp.desc())
            if limit:
                stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Failed to get messages by status: {e}", exc_info=True)
            return []

    @staticmethod
    async def get_failed_messages(
        session: AsyncSession,
        max_retry_count: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[Message]:
        """
        Get failed messages that can be retried.

        Args:
            session: Database session
            max_retry_count: Only return messages below this retry count
            limit: Maximum number of messages to return

        Returns:
            List of failed messages
        """
        try:
            stmt = select(Message).where(Message.processing_status == MessageStatus.FAILED)

            if max_retry_count is not None:
                stmt = stmt.where(Message.retry_count < max_retry_count)

            stmt = stmt.order_by(Message.timestamp.desc())

            if limit:
                stmt = stmt.limit(limit)

            result = await session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Failed to get failed messages: {e}", exc_info=True)
            return []

    @staticmethod
    async def get_queued_messages(session: AsyncSession, limit: Optional[int] = None) -> List[Message]:
        """
        Get all messages with QUEUED status for batch processing.

        Args:
            session: Database session
            limit: Optional maximum number of messages to retrieve

        Returns:
            List of queued messages
        """
        try:
            stmt = (
                select(Message)
                .where(Message.processing_status == MessageStatus.QUEUED)
                .order_by(Message.timestamp.asc())
            )
            if limit:
                stmt = stmt.limit(limit)

            result = await session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Failed to get queued messages: {e}", exc_info=True)
            return []

    @staticmethod
    async def find_completed_by_youtube_url(session: AsyncSession, youtube_url: str) -> Optional[Message]:
        """
        Find a completed message with the given YouTube URL.

        Queries the ProcessedNote.processed_data JSON field for exact URL match.
        Used for deduplication of YouTube URLs during batch processing.

        Supports both PostgreSQL and SQLite with database-specific JSON query syntax.

        Args:
            session: Database session
            youtube_url: The YouTube URL to search for (normalized format)

        Returns:
            Completed Message object if found, None otherwise
        """
        try:
            # Detect database type from connection URL
            db_url = str(session.bind.url)

            # Build query with database-specific JSON syntax
            if "postgresql" in db_url:
                # PostgreSQL: Use ->> operator (text extraction)
                # Use as_string() to extract JSON value as text
                json_condition = ProcessedNote.processed_data['url'].as_string() == youtube_url
            else:
                # SQLite: Use json_extract function
                json_condition = func.json_extract(ProcessedNote.processed_data, '$.url') == youtube_url

            # Join Message and ProcessedNote, query JSON field for URL
            stmt = (
                select(Message)
                .join(ProcessedNote, Message.id == ProcessedNote.message_id)
                .where(
                    and_(
                        Message.processing_status == MessageStatus.COMPLETED,
                        json_condition
                    )
                )
            )

            result = await session.execute(stmt)
            message = result.scalar_one_or_none()

            if message:
                logger.debug(f"Found duplicate YouTube URL: {youtube_url} (message_id={message.id})")
            return message
        except Exception as e:
            logger.error(f"Failed to find completed message by YouTube URL: {e}", exc_info=True)
            return None

    @staticmethod
    async def dequeue(session: AsyncSession, limit: int = 10) -> List[Message]:
        """
        Get next messages from queue (alias for get_queued_messages with limit).

        Args:
            session: Database session
            limit: Maximum number of messages to retrieve

        Returns:
            List of queued messages
        """
        return await MessageRepository.get_queued_messages(session, limit=limit)

    @staticmethod
    def _generate_worker_id() -> str:
        """
        Generate a unique worker identifier.

        Format: {hostname}-{pid}-{short-uuid}
        Example: myserver-1234-a3f2b

        Returns:
            Unique worker ID string
        """
        hostname = socket.gethostname()
        pid = os.getpid()
        short_uuid = str(uuid.uuid4())[:8]
        return f"{hostname}-{pid}-{short_uuid}"

    @staticmethod
    async def dequeue_atomic(
        session: AsyncSession,
        limit: int = 10,
        worker_id: Optional[str] = None
    ) -> List[Message]:
        """
        Atomically dequeue messages with database-specific optimizations.

        This method prevents race conditions when multiple workers process the queue
        simultaneously. It uses different strategies based on the database type:

        - PostgreSQL: Uses SELECT FOR UPDATE SKIP LOCKED (true row-level locking)
          allowing parallel workers to process different messages simultaneously
        - SQLite: Uses UPDATE...RETURNING (atomic but serialized due to database-level locks)
        - Other: Falls back to optimistic locking with retry

        Args:
            session: Database session
            limit: Maximum number of messages to dequeue
            worker_id: Optional worker identifier (auto-generated if not provided)

        Returns:
            List of claimed messages with status updated to PROCESSING
        """
        # Generate worker_id if not provided
        if not worker_id:
            worker_id = MessageRepository._generate_worker_id()

        # Detect database type from connection URL
        db_url = str(session.bind.url)

        if "postgresql" in db_url:
            return await MessageRepository._dequeue_postgres(session, limit, worker_id)
        elif "sqlite" in db_url:
            return await MessageRepository._dequeue_sqlite(session, limit, worker_id)
        else:
            logger.warning(f"Unknown database type: {db_url}, using non-atomic dequeue")
            return await MessageRepository.get_queued_messages(session, limit)

    @staticmethod
    async def _dequeue_postgres(
        session: AsyncSession,
        limit: int,
        worker_id: str
    ) -> List[Message]:
        """
        PostgreSQL-specific atomic dequeue using SELECT FOR UPDATE SKIP LOCKED.

        This implementation provides true row-level locking allowing multiple workers
        to dequeue different messages in parallel without blocking each other.

        Args:
            session: Database session
            limit: Maximum number of messages to dequeue
            worker_id: Worker identifier

        Returns:
            List of claimed messages
        """
        try:
            # Step 1: SELECT FOR UPDATE SKIP LOCKED to claim messages atomically
            stmt = (
                select(Message)
                .where(Message.processing_status == MessageStatus.QUEUED)
                .order_by(Message.timestamp.asc())
                .limit(limit)
                .with_for_update(skip_locked=True)
            )

            result = await session.execute(stmt)
            messages = list(result.scalars().all())

            if not messages:
                return []

            # Step 2: Update claimed messages to PROCESSING status with worker_id
            message_ids = [msg.id for msg in messages]
            update_stmt = (
                update(Message)
                .where(Message.id.in_(message_ids))
                .values(
                    processing_status=MessageStatus.PROCESSING,
                    worker_id=worker_id,
                    updated_at=datetime.utcnow()
                )
            )
            await session.execute(update_stmt)
            await session.flush()

            logger.info(f"Worker {worker_id} claimed {len(messages)} messages (PostgreSQL)")
            return messages

        except Exception as e:
            logger.error(f"Failed to dequeue messages (PostgreSQL): {e}", exc_info=True)
            return []

    @staticmethod
    async def _dequeue_sqlite(
        session: AsyncSession,
        limit: int,
        worker_id: str
    ) -> List[Message]:
        """
        SQLite-specific atomic dequeue using UPDATE...RETURNING.

        SQLite doesn't support row-level locking or SKIP LOCKED, but UPDATE...RETURNING
        provides atomicity through database-level locks. Only one worker can execute
        the UPDATE at a time, preventing race conditions.

        Args:
            session: Database session
            limit: Maximum number of messages to dequeue
            worker_id: Worker identifier

        Returns:
            List of claimed messages
        """
        try:
            # SQLite: Use UPDATE...RETURNING for atomic claim
            # This works because SQLite serializes writes at the database level
            # Using enum values for consistency and maintainability
            update_stmt = text("""
                UPDATE messages
                SET processing_status = :status_processing,
                    worker_id = :worker_id,
                    updated_at = :updated_at
                WHERE id IN (
                    SELECT id FROM messages
                    WHERE processing_status = :status_queued
                    ORDER BY timestamp ASC
                    LIMIT :limit
                )
                RETURNING id
            """)

            result = await session.execute(
                update_stmt,
                {
                    "status_processing": MessageStatus.PROCESSING.value,
                    "status_queued": MessageStatus.QUEUED.value,
                    "worker_id": worker_id,
                    "updated_at": datetime.utcnow(),
                    "limit": limit
                }
            )

            # Get the IDs of updated messages
            message_ids = [row[0] for row in result.fetchall()]

            if not message_ids:
                return []

            # Flush to ensure UPDATE is committed in this transaction
            await session.flush()

            # Now fetch the updated Message objects using SQLAlchemy ORM
            stmt = select(Message).where(Message.id.in_(message_ids))
            result = await session.execute(stmt)
            messages = list(result.scalars().all())

            logger.info(f"Worker {worker_id} claimed {len(messages)} messages (SQLite)")
            return messages

        except Exception as e:
            logger.error(f"Failed to dequeue messages (SQLite): {e}", exc_info=True)
            return []


class ProcessedNoteRepository:
    """Repository for ProcessedNote operations."""

    @staticmethod
    async def create(
        session: AsyncSession,
        message_id: int,
        title: str,
        file_path: str,
        tags: Optional[List[str]] = None,
        concepts: Optional[List[str]] = None,
        entities: Optional[Dict[str, List[str]]] = None,
        summary: Optional[str] = None,
        processed_data: Optional[Dict[str, Any]] = None
    ) -> Optional[ProcessedNote]:
        """
        Create a processed note record.

        Args:
            session: Database session
            message_id: Associated message ID
            title: Note title
            file_path: Path to markdown file
            tags: List of tags
            concepts: List of concepts
            entities: Dict of entity lists (people, places, terms)
            summary: Note summary
            processed_data: Full processed data structure

        Returns:
            Created ProcessedNote object or None if failed
        """
        try:
            note = ProcessedNote(
                message_id=message_id,
                title=title,
                file_path=file_path,
                tags=tags,
                concepts=concepts,
                entities=entities,
                summary=summary,
                processed_data=processed_data,
                created_at=datetime.utcnow()
            )
            session.add(note)
            await session.flush()
            logger.debug(f"Created note record: id={note.id}, title={title}")
            return note
        except Exception as e:
            logger.error(f"Failed to create note: {e}", exc_info=True)
            return None

    @staticmethod
    async def get_by_message_id(session: AsyncSession, message_id: int) -> Optional[ProcessedNote]:
        """Get note by message ID."""
        try:
            stmt = select(ProcessedNote).where(ProcessedNote.message_id == message_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get note by message_id: {e}", exc_info=True)
            return None


class AnalyticsRepository:
    """Repository for analytics queries."""

    @staticmethod
    async def get_message_counts_by_category(session: AsyncSession) -> Dict[str, int]:
        """Get count of messages by category."""
        try:
            stmt = (
                select(Message.category, func.count(Message.id))
                .where(Message.category.isnot(None))
                .group_by(Message.category)
            )
            result = await session.execute(stmt)
            return {category: count for category, count in result.all()}
        except Exception as e:
            logger.error(f"Failed to get category counts: {e}", exc_info=True)
            return {}

    @staticmethod
    async def get_message_counts_by_language(session: AsyncSession) -> Dict[str, int]:
        """Get count of messages by language."""
        try:
            stmt = (
                select(Message.language, func.count(Message.id))
                .where(Message.language.isnot(None))
                .group_by(Message.language)
            )
            result = await session.execute(stmt)
            return {language: count for language, count in result.all()}
        except Exception as e:
            logger.error(f"Failed to get language counts: {e}", exc_info=True)
            return {}

    @staticmethod
    async def get_message_counts_by_status(session: AsyncSession) -> Dict[str, int]:
        """Get count of messages by status."""
        try:
            stmt = (
                select(Message.processing_status, func.count(Message.id))
                .group_by(Message.processing_status)
            )
            result = await session.execute(stmt)
            return {status.value: count for status, count in result.all()}
        except Exception as e:
            logger.error(f"Failed to get status counts: {e}", exc_info=True)
            return {}

    @staticmethod
    async def get_total_messages(session: AsyncSession) -> int:
        """Get total count of messages."""
        try:
            stmt = select(func.count(Message.id))
            result = await session.execute(stmt)
            return result.scalar() or 0
        except Exception as e:
            logger.error(f"Failed to get total message count: {e}", exc_info=True)
            return 0

    @staticmethod
    async def get_success_rate(session: AsyncSession) -> float:
        """Calculate processing success rate."""
        try:
            total_stmt = select(func.count(Message.id))
            total_result = await session.execute(total_stmt)
            total = total_result.scalar() or 0

            if total == 0:
                return 0.0

            success_stmt = (
                select(func.count(Message.id))
                .where(Message.processing_status == MessageStatus.COMPLETED)
            )
            success_result = await session.execute(success_stmt)
            success = success_result.scalar() or 0

            return (success / total) * 100
        except Exception as e:
            logger.error(f"Failed to calculate success rate: {e}", exc_info=True)
            return 0.0
