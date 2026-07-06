from typing import Protocol, Optional
from pathlib import Path

from src.services.typex import SummarizerResult

class INoteService(Protocol):
    """Protocol defining the note service interface."""

    async def generate_note(self, processed_data: SummarizerResult, message_id: Optional[int] = None) -> Path:        
        """
        Generate a note from processed data.

        Args:
            processed_data: SummarizerResult containing structured note data
            message_id: Optional database message ID for storing metadata

        Returns:
            Path to the created note file
        """
        ...
