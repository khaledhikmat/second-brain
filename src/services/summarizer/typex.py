from typing import Dict, List, Protocol, Optional, Any

from src.services.typex import SummarizerResult

class ISummarizerService(Protocol):
    """Protocol defining the summarizer service interface."""

    async def summarize(
            self,
            channel: str,
            message: str,
            category: str,
            language: str = None,
            specified_title: Optional[str] = None,
            metadata: Optional[Dict[str, Any]] = None
        ) -> SummarizerResult:        
        """
        Process an incoming message and create a summary.

        Args:
            channel: The channel to which the summary belongs
            message: The message content
            category: The category of the note
            language: The language of the message
            specified_title: The title of the summary (if specified)
            metadata: Optional dictionary containing additional metadata for the note
        """
        ...
