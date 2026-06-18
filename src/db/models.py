"""
SQLAlchemy models for message storage and replay functionality.

Designed to support both SQLite (development) and PostgreSQL (production).
"""

from datetime import datetime
from typing import Optional
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
    source = Column(String(50), nullable=False, index=True)  # "telegram", "http", "batch"
    source_message_id = Column(String(255), nullable=True)  # External message ID (e.g., Telegram message ID)
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
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    note = relationship("ProcessedNote", back_populates="message", uselist=False, cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("idx_message_status_timestamp", "processing_status", "timestamp"),
        Index("idx_message_category_language", "category", "language"),
    )

    def __repr__(self):
        return f"<Message(id={self.id}, status={self.processing_status}, category={self.category})>"


class ProcessedNote(Base):
    """
    Successfully processed notes with extracted metadata.

    Stores structured data extracted by Claude and the file path to the markdown note.
    """
    __tablename__ = "processed_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False, unique=True)
    title = Column(String(500), nullable=False)
    tags = Column(JSON, nullable=True)  # List of strings
    concepts = Column(JSON, nullable=True)  # List of strings
    entities = Column(JSON, nullable=True)  # Dict with people, places, terms lists
    summary = Column(Text, nullable=True)  # 1-2 sentence summary
    file_path = Column(String(1000), nullable=False, unique=True)  # Path to markdown file
    processed_data = Column(JSON, nullable=True)  # Full processed data structure
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Relationships
    message = relationship("Message", back_populates="note")

    # Indexes
    __table_args__ = (
        Index("idx_note_title", "title"),
        Index("idx_note_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<ProcessedNote(id={self.id}, title={self.title})>"
