from typing import Protocol, Optional, List, Dict, Any

from services.setting.typex import ISettingService
from services.logger.typex import ILoggerService

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    Enum as SQLEnum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()

class MessageStatus(str, enum.Enum):
    """Status of message processing (used for both immediate and batch modes)."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    IGNORED = "ignored"  # Message skipped (e.g., duplicate YouTube URL)


class Message(Base):
    """
    All incoming messages from Telegram, HTTP API, or batch processing.

    Tracks the complete lifecycle of each message from receipt to processing completion.
    Supports both immediate mode (PROCESSING → COMPLETED/FAILED) and batch mode (QUEUED → PROCESSING → COMPLETED/FAILED).
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    user_id = Column(String(255), nullable=True)  # Telegram user ID or API client ID
    source = Column(String(50), nullable=True, index=True)  # "youtube, pdf, etc" (optional)
    source_reference = Column(String(255), nullable=True)  # External message ID (e.g., YouTube URL, pdf file path)
    channel = Column(String(50), nullable=True, index=True)  # Communication channel (e.g., "telegram", "http")
    category = Column(String(100), nullable=True, index=True)  # One of 8 predefined categories
    language = Column(String(10), nullable=True, index=True)  # "ar", "en", or detected language
    raw_text = Column(Text, nullable=False)  # Original message text
    processing_status = Column(
        SQLEnum(MessageStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=MessageStatus.QUEUED,
        index=True
    )
    worker_id = Column(String(100), nullable=True, index=True)  # Worker that claimed this message
    error_message = Column(Text, nullable=True)  # Error details if failed
    retry_count = Column(Integer, default=0)  # Number of processing attempts
    queued_at = Column(DateTime, nullable=True)  # When the message was queued
    processed_at = Column(DateTime, nullable=True)  # When the message was completed/failed
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index("idx_message_status_timestamp", "processing_status", "timestamp"),
        Index("idx_message_category_language", "category", "language"),
    )

    def __repr__(self):
        return f"<Message(id={self.id}, status={self.processing_status}, category={self.category})>"

class IDataService(Protocol):
    """Protocol defining the database interface."""
    def __init__(self, setting: ISettingService, logger: ILoggerService):
        """
        Initialize the database with settings and logger.

        Args:
            setting: An instance of ISetting for configuration
            logger: An instance of ILogger for logging
        """
        self.setting = setting
        self.logger = logger

    ## Management methods
    async def initialize(self) -> bool:
        """
        Initialize the database connection and create tables if they don't exist.

        Returns:
            True if initialization successful, False otherwise
        """
        ...

    async def is_database_available(self) -> bool:
        """
        Check if the database is available and healthy.

        Returns:
            True if the database is available and healthy, False otherwise
        """
        ...

    async def finalize(self) -> bool:
        """
        Finalize the database connection.

        Returns:
            True if finalization successful, False otherwise
        """
        ...


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
        Create a new message in the database.

        Returns:
            The path to the logs directory
        """
        ...

    async def update_message(self, 
        message_id: int,
        status: MessageStatus,
        error_message: Optional[str] = None,
        language: Optional[str] = None,
        source: Optional[str] = None,
        source_reference: Optional[str] = None
    ) -> bool:
        """
        Update an existing message in the database by its ID.

        Returns:
            True if the message was updated, False otherwise
        """
        ...

    async def increment_message_retry_count(selfmessage_id: int) -> bool:
        """
        Increment the retry count for a message.

        Returns:
            True if the retry count was incremented, False otherwise
        """
        ...

    async def get_message_by_id(self, message_id: int) -> Optional[Message]:
        """
        Get a message by its ID.

        Returns:
            The message if found, None otherwise
        """
        ...

    async def get_messages_by_status(self, status: MessageStatus, limit: Optional[int] = None) -> List[Message]:
        """
        Get messages by their processing status.

        Returns:
            A list of messages with the specified status
        """
        ...

    async def get_failed_messages(self, max_retry_count: Optional[int] = None, limit: Optional[int] = None) -> List[Message]:
        """
        Get messages that have failed processing.

        Returns:
            A list of failed messages
        """
        ...

    async def get_queued_messages(self, limit: Optional[int] = None) -> List[Message]:
        """
        Get messages that are queued for processing.

        Returns:
            A list of queued messages
        """
        ...

    async def dequeue_messages(self, limit: int, worker_id: str) -> List[Message]:
        """
        Atomically dequeue messages for processing.

        Returns:
            A list of messages to be processed
        """
        ...

    ## Stats-related methods
    async def get_message_counts_by_category(self) -> Dict[str, int]:
        """
        Get the count of messages by their category.

        Returns:
            A dictionary mapping categories to their respective counts
        """
        ...

    async def get_message_counts_by_language(self) -> Dict[str, int]:
        """
        Get the count of messages by their language.

        Returns:
            A dictionary mapping languages to their respective counts
        """
        ...

    async def get_total_messages(self) -> int:
        """
        Get the total count of messages.

        Returns:
            The total count of messages
        """
        ...

    async def get_success_rate(self) -> float:
        """
        Get the success rate of message processing.

        Returns:
            The success rate as a float
        """
        ...