from typing import Any, Dict, Optional

from src.services.setting.typex import ISettingService
from src.services.logger.typex import ILoggerService
from src.services.typex import SummarizerResult


class PdfSummarizerService:
    def __init__(self, setting: ISettingService, logger: ILoggerService):
        self._setting = setting
        self._logger = logger

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
        Process an incoming message and create a note.

        Args:
            channel: The channel to which the summary belongs
            message: The incoming message
            category: The category of the note
            language: The language of the message
            specified_title: The title of the note (if specified)
            specified_category: The category of the note (if specified)
            metadata: Optional dictionary containing additional metadata for the note

        Returns:
            SummarizerResult: A structured result containing the summary and metadata.
        """
        return NotImplementedError("PDF summarizer processing is not implemented yet.")

