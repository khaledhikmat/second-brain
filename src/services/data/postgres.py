from datetime import datetime
from typing import Protocol, Optional, List, Dict, Any
import asyncio

from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool, StaticPool
from sqlalchemy import text
from sqlalchemy import select, update, delete, func, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession

from services.setting.typex import ISettingService
from services.logger.typex import ILoggerService
from services.data.typex import Base, Message, MessageStatus

class PostgresDataService:
    def __init__(self, setting: ISettingService, logger: ILoggerService):
        self._setting = setting
        self._logger = logger

    ## Management methods
    async def initialize(self) -> bool:
        """
        Initialize database connection and create tables.

        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            self.engine = create_async_engine(
                self._setting.get_database_url(),
                echo=self._setting.get_database_echo(),
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
            async with self._get_session() as session:
                await session.execute(text("SELECT 1"))

            self._logger.info(f"Database initialized successfully: {self._mask_url(self._setting.get_database_url())}")
            return True

        except Exception as e:
            self._logger.error(f"Failed to initialize database: {e}")
            self._is_available = False
            return False

    async def is_database_available(self) -> bool:
        """
        Perform health check on database connection.

        Returns:
            bool: True if database is healthy, False otherwise
        """
        if not self._is_available:
            return False

        try:
            async with self._get_session() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            self._logger.error(f"Database health check failed: {e}")
            self._is_available = False
            return False

    async def finalize(self):
        """Close database connections."""
        if self.engine:
            try:
                await self.engine.dispose()
                self._logger.info("Database connections closed")
            except asyncio.CancelledError:
                # Suppress cancellation errors during shutdown
                self._logger.debug("Database cleanup cancelled during shutdown")
            except Exception as e:
                self._logger.error(f"Error closing database connections: {e}")

    ## Message-related methods
    async def create_message(self,
            raw_text: str,
            category: str,
            channel: str,
            language: Optional[str] = None,
            source: Optional[str] = None,
            source_reference: Optional[str] = None
        ) -> Optional[Message]:
        """
        Create a new message record.

        Args:
            raw_text: Original message text
            category: Optional message category
            channel: Message channel ("telegram", "http")
            source: Optional source of the message
            source_reference: Optional reference to the source
            language: Optional detected language

        Returns:
            Created Message object or None if failed
        """
        try:
            async with self._get_session() as session:
                now = datetime.utcnow()
                message = Message(
                    raw_text=raw_text,
                    category=category,
                    channel=channel, 
                    source=source,  
                    source_reference=source_reference,
                    language=language,
                    timestamp=now,
                    queued_at=now,  # Set queued_at when message is created
                    processing_status=MessageStatus.QUEUED  # Default status
                )
                session.add(message)
                await session.flush()  # Get the ID without committing
                self._logger.debug(f"Created message record: id={message.id}, channel={channel}, status={message.processing_status}")
                return message
        except Exception as e:
            self._logger.error(f"Failed to create message: {e}")
            return None

    async def update_message(self,
        message_id: int,
        status: MessageStatus,
        error_message: Optional[str] = None,
        language: Optional[str] = None,
        source: Optional[str] = None,
        source_reference: Optional[str] = None
    ) -> bool:
        """
        Update message processing status.

        Args:
            message_id: Message ID
            status: New status
            error_message: Optional error message if failed
            source: Optional source of the message
            source_reference: Optional reference to the source
            language: Optional language (if detected during processing)

        Returns:
            True if update successful, False otherwise
        """
        try:
            async with self._get_session() as session:
                now = datetime.utcnow()
                update_data = {
                    "processing_status": status,
                    "updated_at": now
                }

                # Set processed_at when message reaches terminal state
                if status in (MessageStatus.COMPLETED, MessageStatus.FAILED, MessageStatus.IGNORED):
                    update_data["processed_at"] = now

                # Set queued_at when message is queued
                if status == MessageStatus.QUEUED:
                    update_data["queued_at"] = now

                if error_message:
                    update_data["error_message"] = error_message
                if source:
                    update_data["source"] = source
                if source_reference:
                    update_data["source_reference"] = source_reference
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
                    self._logger.debug(f"Updated message {message_id} status to {status}")
                else:
                    self._logger.warning(f"No message found with id={message_id}")
                return success
        except Exception as e:
            self._logger.error(f"Failed to update message status: {e}")
            return False
    
    async def increment_message_retry_count(self, message_id: int) -> bool:
        """
        Increment the retry count for a message.

        Returns:
            True if the retry count was incremented, False otherwise
        """
        try:
            async with self._get_session() as session:
                stmt = (
                    update(Message)
                    .where(Message.id == message_id)
                    .values(retry_count=Message.retry_count + 1, updated_at=datetime.utcnow())
                )
                result = await session.execute(stmt)
                await session.flush()
                return result.rowcount > 0
        except Exception as e:
            self._logger.error(f"Failed to increment retry count: {e}")
            return False

    async def get_message_by_id(self, message_id: int) -> Optional[Message]:
        """
        Get a message by its ID.

        Returns:
            The message if found, None otherwise
        """
        try:
            async with self._get_session() as session:
                stmt = select(Message).where(Message.id == message_id)
                result = await session.execute(stmt)
                return result.scalar_one_or_none()
        except Exception as e:
            self._logger.error(f"Failed to get message by id: {e}")
            return None

    async def get_messages_by_status(self, status: MessageStatus, limit: Optional[int] = None) -> List[Message]:
        """
        Get messages by their processing status.

        Returns:
            A list of messages with the specified status
        """
        try:
            async with self._get_session() as session:
                stmt = select(Message).where(Message.processing_status == status).order_by(Message.timestamp.desc())
                if limit:
                    stmt = stmt.limit(limit)
                result = await session.execute(stmt)
                return List(result.scalars().all())
        except Exception as e:
            self._logger.error(f"Failed to get messages by status: {e}")
            return []

    async def get_failed_messages(self, max_retry_count: Optional[int] = None, limit: Optional[int] = None) -> List[Message]:
        """
        Get failed messages that can be retried.

        Args:
            max_retry_count: Only return messages below this retry count
            limit: Maximum number of messages to return

        Returns:
            List of failed messages
        """
        try:
            async with self._get_session() as session:
                stmt = select(Message).where(Message.processing_status == MessageStatus.FAILED)

                if max_retry_count is not None:
                    stmt = stmt.where(Message.retry_count < max_retry_count)

                stmt = stmt.order_by(Message.timestamp.desc())

                if limit:
                    stmt = stmt.limit(limit)

                result = await session.execute(stmt)
                return List(result.scalars().all())
        except Exception as e:
            self._logger.error(f"Failed to get failed messages: {e}")
            return []

    async def get_queued_messages(self, limit: Optional[int] = None) -> List[Message]:
        """
        Get all messages with QUEUED status.

        Args:
            limit: Optional maximum number of messages to retrieve

        Returns:
            List of queued messages
        """
        try:
            async with self._get_session() as session:
                stmt = (
                    select(Message)
                    .where(Message.processing_status == MessageStatus.QUEUED)
                    .order_by(Message.timestamp.asc())
                )
                if limit:
                    stmt = stmt.limit(limit)

                result = await session.execute(stmt)
                return List(result.scalars().all())
        except Exception as e:
            self._logger.error(f"Failed to get queued messages: {e}")
            return []

    async def dequeue_messages(self, limit: int, worker_id: str) -> List[Message]:
        """
        Atomically dequeue messages with database-specific optimizations.

        This method prevents race conditions when multiple workers process the queue
        simultaneously. It uses different strategies based on the database type:

        - Uses SELECT FOR UPDATE SKIP LOCKED (true row-level locking)
          allowing parallel workers to process different messages simultaneously

        Args:
            limit: Maximum number of messages to dequeue
            worker_id: Worker identifier

        Returns:
            List of claimed messages with status updated to PROCESSING
        """
        try:
            async with self._get_session() as session:
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

                self._logger.info(f"Worker {worker_id} claimed {len(messages)} messages (PostgreSQL)")
                return messages
        except Exception as e:
            self._logger.error(f"Failed to dequeue messages (PostgreSQL): {e}")
            return []

    ## Stats-related methods
    async def get_message_counts_by_category(self) -> Dict[str, int]:
        """
        Get the count of messages by their category.

        Returns:
            A dictionary mapping categories to their respective counts
        """
        try:
            async with self._get_session() as session:
                stmt = (
                    select(Message.category, func.count(Message.id))
                    .where(Message.category.isnot(None))
                    .group_by(Message.category)
                )
                result = await session.execute(stmt)
                return {category: count for category, count in result.all()}
        except Exception as e:
            self._logger.error(f"Failed to get category counts: {e}")
            return {}

    async def get_message_counts_by_language(self) -> Dict[str, int]:
        """
        Get the count of messages by their language.

        Returns:
            A dictionary mapping languages to their respective counts
        """
        try:
            async with self._get_session() as session:
                stmt = (
                    select(Message.language, func.count(Message.id))
                    .where(Message.language.isnot(None))
                    .group_by(Message.language)
                )
                result = await session.execute(stmt)
                return {language: count for language, count in result.all()}
        except Exception as e:
            self._logger.error(f"Failed to get language counts: {e}")
            return {}

    async def get_total_messages(self) -> int:
        """
        Get the total count of messages.

        Returns:
            The total count of messages
        """
        try:
            async with self._get_session() as session:
                stmt = select(func.count(Message.id))
                result = await session.execute(stmt)
                return result.scalar() or 0
        except Exception as e:
            self._logger.error(f"Failed to get total message count: {e}")
            return 0

    async def get_success_rate(self) -> float:
        """
        Get the success rate of message processing.

        Returns:
            The success rate as a float
        """
        try:
            async with self._get_session() as session:
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
            self._logger.error(f"Failed to calculate success rate: {e}")
            return 0.0

    #### PRIVATE METHODS ####

    @asynccontextmanager
    async def _get_session(self):
        """
        Get a database session with automatic cleanup.

        Usage:
            async with db_manager._get_session() as session:
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
    async def _get_session_safe(self):
        """
        Get a database session with graceful degradation.

        If database is unavailable, yields None instead of raising an error.
        Use this for non-critical operations where the system should continue
        even if database writes fail.

        Usage:
            async with db_manager._get_session_safe() as session:
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
            self._logger.warning("Database unavailable, operating in degraded mode")
            yield None
            return

        session = self.session_factory()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            self._logger.error(f"Database operation failed: {e}")
            # Don't re-raise - allow system to continue
        finally:
            await session.close()

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



