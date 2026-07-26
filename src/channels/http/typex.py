from typing import Optional, Protocol
from fastapi import FastAPI
from pydantic import BaseModel, Field

class NoteRequest(BaseModel):
    """Request model for creating a note from text."""
    message: str = Field(..., description="The message text or URL to process")
    category: str = Field(None, description="Optional category override")
    language: str = Field(None, description="Optional language override")

class NoteResponse(BaseModel):
    """Response model for note operations."""
    success: bool = True
    error: Optional[str] = None
    detail: Optional[str] = None

class IHttpHandler(Protocol):
    """Protocol defining the HTTP handler interface."""

    async def start(self) -> None:
        """Start the HTTP API server."""
        ...

    async def stop(self) -> None:
        """Stop the HTTP API server."""
        ...
