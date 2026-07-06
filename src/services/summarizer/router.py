from typing import Any, Dict, Optional

from src.helpers.utilities import is_arabic, is_english, is_text_message, is_youtube_url_messagae, is_pdf_message

from src.services.setting.typex import ISettingService
from src.services.logger.typex import ILoggerService
from src.services.typex import SummarizerResult
from src.services.summarizer.typex import ISummarizerService

class RouterSummarizerService:
    def __init__(self, setting: ISettingService, logger: ILoggerService, text_processor: ISummarizerService, youtube_processor: ISummarizerService, pdf_processor: ISummarizerService):
        self._setting = setting
        self._logger = logger
        self._text_processor = text_processor
        self._youtube_processor = youtube_processor
        self._pdf_processor = pdf_processor

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
        if language is None:
            language = "Arabic" if is_arabic(actual_message) else "English"

        # Route to different processors based on message type
        if is_youtube_url_messagae(message):
            return await self._youtube_processor.summarize(
                channel=channel,
                message=message,
                category=category,
                language=language,
                specified_title=specified_title,
                metadata=metadata
            )
        elif is_pdf_message(message):
            return await self._pdf_processor.summarize(
                channel=channel,
                message=message,
                category=category,
                language=language,
                specified_title=specified_title,
                metadata=metadata
            )
        
        return await self._text_processor.summarize(
            channel=channel,
            message=message,
            category=category,
            language=language,
            specified_title=specified_title,
            metadata=metadata
        )

