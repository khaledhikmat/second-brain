"""HTTP API handler using FastAPI."""

import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

from ..processors.claude_processor import ClaudeProcessor
from ..processors.note_generator import ObsidianNoteGenerator
from ..utils.language_detector import detect_language
from ..middleware.auth import create_api_key_dependency
from ..db.database import get_db_manager
from ..db.repository import MessageRepository
from ..db.models import MessageStatus
from ..services.message_replay import MessageReplayService
from ..services.analytics import AnalyticsService

logger = logging.getLogger(__name__)


# Request/Response Models
class NoteRequest(BaseModel):
    """Request model for creating a note from text."""
    message: str = Field(..., description="The message text to process")
    category: Optional[str] = Field(None, description="Optional category override")


class YouTubeRequest(BaseModel):
    """Request model for creating a note from YouTube video."""
    url: str = Field(..., description="YouTube video URL")
    category: Optional[str] = Field(None, description="Optional category override")


class NoteResponse(BaseModel):
    """Response model for note creation."""
    success: bool
    note_path: Optional[str] = None
    note_id: Optional[str] = None
    title: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = None
    created_at: Optional[str] = None
    # For queued messages
    message: Optional[str] = None
    message_id: Optional[int] = None
    status: Optional[str] = None


class ErrorResponse(BaseModel):
    """Response model for errors."""
    success: bool = False
    error: str
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    service: str
    timestamp: str


class ReplayResponse(BaseModel):
    """Response model for replay operations."""
    success: bool
    message: str
    replayed_count: Optional[int] = None
    skipped_count: Optional[int] = None


class HTTPHandler:
    """HTTP API handler for notes processor."""

    def __init__(
        self,
        claude_processor: ClaudeProcessor,
        note_generator: ObsidianNoteGenerator,
        api_key: str,
        youtube_processor: Optional[Any] = None,
        batch_mode: bool = False
    ):
        """
        Initialize HTTP API handler.

        Args:
            claude_processor: Claude AI processor instance
            note_generator: Obsidian note generator instance
            api_key: API key for authentication
            youtube_processor: Optional YouTube processor instance
            batch_mode: Whether to queue messages for batch processing
        """
        self.claude_processor = claude_processor
        self.note_generator = note_generator
        self.api_key = api_key
        self.youtube_processor = youtube_processor
        self.batch_mode = batch_mode

        # Initialize services
        self.replay_service = MessageReplayService()
        self.analytics_service = AnalyticsService()

        # Create FastAPI app
        self.app = FastAPI(
            title="Notes Processor API",
            description="HTTP API for creating structured notes from text and YouTube videos",
            version="1.0.0"
        )

        # Create API key dependency
        self.verify_api_key = create_api_key_dependency(api_key)

        # Setup routes
        self._setup_routes()

        # Include dashboard router
        from src.config import DASHBOARD_ENABLED
        if DASHBOARD_ENABLED:
            from src.handlers.dashboard_handler import router as dashboard_router
            self.app.include_router(dashboard_router)
            logger.info("Dashboard enabled and routes registered")

        logger.info("HTTP API handler initialized")

    def _setup_routes(self):
        """Setup FastAPI routes."""

        @self.app.get("/health", response_model=HealthResponse, tags=["Health"])
        async def health_check():
            """Health check endpoint."""
            return HealthResponse(
                status="healthy",
                service="notes-processor-api",
                timestamp=datetime.now().isoformat()
            )

        @self.app.post(
            "/api/v1/notes",
            response_model=NoteResponse,
            responses={
                401: {"model": ErrorResponse},
                500: {"model": ErrorResponse}
            },
            tags=["Notes"]
        )
        async def create_note(
            request: NoteRequest,
            api_key: str = Depends(self.verify_api_key)
        ):
            """
            Create a note from text message.

            Processes the message with Claude AI and creates a structured Obsidian note.
            """
            try:
                logger.info(f"Received note creation request (length: {len(request.message)} chars)")

                # Build message text with category prefix if provided
                message_text = request.message
                if request.category:
                    message_text = f"{request.category} -> {message_text}"

                # Check if batch mode is enabled
                if self.batch_mode:
                    # Queue the message for batch processing
                    db_manager = get_db_manager()
                    if not db_manager or not db_manager.is_available:
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Database unavailable - cannot queue in batch mode"
                        )

                    async with db_manager.get_session() as session:
                        # Queue the message
                        message = await MessageRepository.create(
                            session,
                            raw_text=message_text,
                            source="http_api",
                            category=request.category,
                            processing_status=MessageStatus.QUEUED
                        )

                        if not message:
                            raise HTTPException(
                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Failed to queue message"
                            )

                        logger.info(f"Queued message for batch processing: message_id={message.id}")

                        return NoteResponse(
                            success=True,
                            message="Message queued for batch processing",
                            message_id=message.id,
                            status="queued"
                        )

                # Immediate processing (non-batch mode)
                # Process message
                note_path = await self._process_message(message_text)

                # Read note metadata
                note_data = self._read_note_metadata(note_path)

                return NoteResponse(
                    success=True,
                    note_path=str(note_path),
                    note_id=note_data.get("id", ""),
                    title=note_data.get("title", ""),
                    category=note_data.get("category", ""),
                    language=note_data.get("language", ""),
                    created_at=note_data.get("created", "")
                )

            except Exception as e:
                logger.error(f"Error creating note: {e}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to create note: {str(e)}"
                )

        @self.app.post(
            "/api/v1/youtube",
            response_model=NoteResponse,
            responses={
                401: {"model": ErrorResponse},
                400: {"model": ErrorResponse},
                500: {"model": ErrorResponse}
            },
            tags=["Notes"]
        )
        async def create_note_from_youtube(
            request: YouTubeRequest,
            api_key: str = Depends(self.verify_api_key)
        ):
            """
            Create a note from YouTube video transcript.

            Fetches the video transcript, processes it with Claude AI,
            and creates a structured Obsidian note.
            """
            if not self.youtube_processor:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="YouTube transcription is not enabled. Set YOUTUBE_ENABLED=true in configuration."
                )

            try:
                logger.info(f"Received YouTube transcription request: {request.url}")

                # Check if batch mode is enabled
                if self.batch_mode:
                    # Queue the YouTube URL for batch processing
                    db_manager = get_db_manager()
                    if not db_manager or not db_manager.is_available:
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Database unavailable - cannot queue in batch mode"
                        )

                    async with db_manager.get_session() as session:
                        # Format message with category if provided
                        message_text = f"{request.category} -> {request.url}" if request.category else request.url

                        # Queue the URL
                        message = await MessageRepository.create(
                            session,
                            raw_text=message_text,
                            source="http_api",
                            category=request.category,
                            processing_status=MessageStatus.QUEUED
                        )

                        if not message:
                            raise HTTPException(
                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Failed to queue YouTube URL"
                            )

                        logger.info(f"Queued YouTube URL for batch processing: message_id={message.id}")

                        return NoteResponse(
                            success=True,
                            message="YouTube URL queued for batch processing",
                            message_id=message.id,
                            status="queued"
                        )

                # Immediate processing (non-batch mode)
                # Process YouTube video (returns dict with content, title, category, etc.)
                youtube_data = await self.youtube_processor.process_youtube_url(
                    request.url,
                    category=request.category
                )

                # Process the transcript as a regular message with explicit metadata
                note_path = await self._process_message(
                    youtube_data["content"],
                    title=youtube_data.get("title"),
                    category=youtube_data.get("category"),
                    url=youtube_data.get("url")
                )

                # Read note metadata
                note_data = self._read_note_metadata(note_path)

                return NoteResponse(
                    success=True,
                    note_path=str(note_path),
                    note_id=note_data.get("id", ""),
                    title=note_data.get("title", ""),
                    category=note_data.get("category", ""),
                    language=note_data.get("language", ""),
                    created_at=note_data.get("created", "")
                )

            except ValueError as e:
                # Invalid URL or video not found
                logger.error(f"Invalid YouTube request: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e)
                )
            except Exception as e:
                logger.error(f"Error processing YouTube video: {e}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to process YouTube video: {str(e)}"
                )

        @self.app.get(
            "/api/v1/messages/failed",
            responses={401: {"model": ErrorResponse}},
            tags=["Messages"]
        )
        async def get_failed_messages(
            limit: Optional[int] = None,
            api_key: str = Depends(self.verify_api_key)
        ):
            """Get list of failed messages that can be replayed."""
            try:
                messages = await self.replay_service.get_failed_messages(limit=limit)
                return {"messages": messages, "count": len(messages)}
            except Exception as e:
                logger.error(f"Error getting failed messages: {e}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(e)
                )

        @self.app.post(
            "/api/v1/replay/{message_id}",
            response_model=ReplayResponse,
            responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
            tags=["Replay"]
        )
        async def replay_message(
            message_id: int,
            api_key: str = Depends(self.verify_api_key)
        ):
            """Replay a specific failed message."""
            try:
                result = await self.replay_service.replay_message(message_id)

                if not result["success"]:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND if "not found" in result.get("error", "").lower() else status.HTTP_400_BAD_REQUEST,
                        detail=result.get("error", "Unknown error")
                    )

                return ReplayResponse(
                    success=True,
                    message=f"Message {message_id} queued for replay",
                    replayed_count=1
                )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error replaying message: {e}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(e)
                )

        @self.app.post(
            "/api/v1/replay/batch",
            response_model=ReplayResponse,
            responses={401: {"model": ErrorResponse}},
            tags=["Replay"]
        )
        async def replay_all_failed(
            limit: Optional[int] = None,
            api_key: str = Depends(self.verify_api_key)
        ):
            """Replay all failed messages."""
            try:
                result = await self.replay_service.replay_all_failed(limit=limit)

                if not result["success"]:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=result.get("error", "Unknown error")
                    )

                return ReplayResponse(
                    success=True,
                    message=f"Replayed {result['replayed_count']} messages, skipped {result['skipped_count']}",
                    replayed_count=result["replayed_count"],
                    skipped_count=result["skipped_count"]
                )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error replaying messages: {e}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(e)
                )

        @self.app.get(
            "/api/v1/analytics/summary",
            responses={401: {"model": ErrorResponse}},
            tags=["Analytics"]
        )
        async def get_analytics_summary(
            api_key: str = Depends(self.verify_api_key)
        ):
            """Get summary analytics."""
            try:
                summary = await self.analytics_service.get_summary()
                return summary
            except Exception as e:
                logger.error(f"Error getting analytics: {e}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(e)
                )

        @self.app.get(
            "/api/v1/analytics/categories",
            responses={401: {"model": ErrorResponse}},
            tags=["Analytics"]
        )
        async def get_category_stats(
            api_key: str = Depends(self.verify_api_key)
        ):
            """Get category statistics."""
            try:
                stats = await self.analytics_service.get_category_stats()
                return stats
            except Exception as e:
                logger.error(f"Error getting category stats: {e}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(e)
                )

        @self.app.get(
            "/api/v1/analytics/processing",
            responses={401: {"model": ErrorResponse}},
            tags=["Analytics"]
        )
        async def get_processing_stats(
            api_key: str = Depends(self.verify_api_key)
        ):
            """Get processing statistics."""
            try:
                stats = await self.analytics_service.get_processing_stats()
                return stats
            except Exception as e:
                logger.error(f"Error getting processing stats: {e}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(e)
                )

        @self.app.get(
            "/api/v1/queue",
            responses={401: {"model": ErrorResponse}},
            tags=["Queue"]
        )
        async def get_queue_status(
            api_key: str = Depends(self.verify_api_key)
        ):
            """Get queue status (messages with QUEUED status)."""
            try:
                db_manager = get_db_manager()
                if not db_manager or not db_manager.is_available:
                    return {"error": "Database not available", "queue": []}

                from ..db.repository import MessageRepository
                async with db_manager.get_session() as session:
                    queued_messages = await MessageRepository.dequeue(session, limit=100)
                    return {
                        "queued_count": len(queued_messages),
                        "queue": [
                            {
                                "id": msg.id,
                                "timestamp": msg.timestamp.isoformat(),
                                "status": msg.processing_status.value,
                                "text_preview": msg.raw_text[:100] + "..." if len(msg.raw_text) > 100 else msg.raw_text
                            }
                            for msg in queued_messages
                        ]
                    }
            except Exception as e:
                logger.error(f"Error getting queue status: {e}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(e)
                )

    async def _process_message(
        self,
        message_text: str,
        user_id: str = "http_api",
        title: Optional[str] = None,
        category: Optional[str] = None,
        url: Optional[str] = None
    ) -> Path:
        """
        Process a message and create a note.

        Args:
            message_text: The message text to process
            user_id: User identifier for tracking
            title: Optional explicit title (e.g., from YouTube video)
            category: Optional explicit category
            url: Optional source URL (e.g., YouTube video URL)

        Returns:
            Path to the created note
        """
        message_id = None
        db_manager = get_db_manager()

        # Track partial information for error handling
        detected_language = None
        category_for_db = category  # Use provided category if available

        # Store message in database
        if db_manager and db_manager.is_available:
            try:
                async with db_manager.get_session_safe() as session:
                    if session:
                        message = await MessageRepository.create(
                            session,
                            raw_text=message_text,
                            source="http",
                            user_id=user_id
                        )
                        if message:
                            message_id = message.id
                            logger.info(f"Stored message in database: id={message_id}")
            except Exception as e:
                logger.error(f"Failed to store message: {e}", exc_info=True)

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

            # Detect language (store for error handling)
            try:
                detected_language = detect_language(message_text)
                logger.info(f"Detected language: {detected_language}")
            except Exception as e:
                logger.warning(f"Could not detect language: {e}")
                detected_language = None

            # Process with Claude (with explicit title and category if provided)
            processed_data = self.claude_processor.process_message(
                message_text,
                detected_language,
                specified_title=title,
                specified_category=category
            )

            # Add URL to processed data if provided (e.g., YouTube video URL)
            if url:
                processed_data["url"] = url

            # Add source information
            processed_data["source"] = "http"

            # Update category_for_db with final category from processed_data
            if not category_for_db:
                category_for_db = processed_data.get("category")

            # Generate note (will also store note metadata if message_id provided)
            note_path = self.note_generator.generate_note(processed_data, message_id)

            # Update status to COMPLETED
            if message_id and db_manager and db_manager.is_available:
                async with db_manager.get_session_safe() as session:
                    if session:
                        await MessageRepository.update_status(
                            session,
                            message_id,
                            MessageStatus.COMPLETED,
                            category=category_for_db,
                            language=detected_language
                        )

            logger.info(f"Created note: {note_path}")
            return note_path

        except Exception as e:
            # Update status to FAILED, preserving whatever information we gathered
            if message_id and db_manager and db_manager.is_available:
                async with db_manager.get_session_safe() as session:
                    if session:
                        await MessageRepository.update_status(
                            session,
                            message_id,
                            MessageStatus.FAILED,
                            error_message=str(e),
                            category=category_for_db,  # Preserve category from request
                            language=detected_language  # May be None if detection failed
                        )
            raise

    def _read_note_metadata(self, note_path: Path) -> Dict[str, Any]:
        """
        Read metadata from a note's YAML frontmatter.

        Args:
            note_path: Path to the note file

        Returns:
            Dictionary with note metadata
        """
        import yaml

        try:
            with open(note_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract YAML frontmatter
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1])
                    return frontmatter

        except Exception as e:
            logger.error(f"Error reading note metadata: {e}")

        return {}

    async def start(self, host: str, port: int):
        """
        Start the HTTP API server.

        Args:
            host: Host to bind to
            port: Port to bind to
        """
        logger.info(f"Starting HTTP API server on {host}:{port}")

        config = uvicorn.Config(
            self.app,
            host=host,
            port=port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()
