from typing import Protocol, Optional, List
from pathlib import Path

from services.summarizer.typex import SummarizerResult

class INoteService(Protocol):
    """Protocol defining the note service interface."""

    async def generate_note(self, processed_data: SummarizerResult, message_id: Optional[int] = None) -> Optional [List[Path]]:       
        """
        Generate a note from processed data.

        Args:
            processed_data: SummarizerResult containing structured note data
            message_id: Optional database message ID for storing metadata

        Returns:
            Returns a list of note paths
        """
        ...
