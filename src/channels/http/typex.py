from typing import Optional, Protocol
from fastapi import FastAPI
from pydantic import BaseModel, Field

class NoteRequest(BaseModel):
    """Request model for creating a note from text."""
    message: str = Field(..., description="The message text or URL to process")
    category: str = Field(None, description="Optional category override")

class NoteResponse(BaseModel):
    """Response model for note operations."""
    success: bool = True
    error: Optional[str] = None
    detail: Optional[str] = None

class IHttpHandler(Protocol):
    """Protocol defining the HTTP handler interface."""

    def get_app(self) -> FastAPI:
        """
        Get the FastAPI application instance.

        Returns:
            The FastAPI application
        """
        ...

    async def initialize(self) -> None:
        """Initialize the HTTP handler."""
        ...

    async def shutdown(self) -> None:
        """Cleanup when shutting down."""
        ...
