from typing import Any, Dict, Optional, List
from datetime import datetime

from google import genai
from google.genai import types

from services.setting.typex import ISettingService
from services.logger.typex import ILoggerService
from services.summarizer.typex import SummarizerResult, produce_summarization_prompt, produce_title_prompt, process_response, create_fallback_structure

class GeminiTextSummarizerService:
    def __init__(self, setting: ISettingService, logger: ILoggerService):
        self._setting = setting
        self._logger = logger

    async def summarize(
            self,
            channel: str,
            category: str,
            language: str,
            message: str,
            metadata: Optional[Dict[str, Any]] = None
        ) -> Optional [SummarizerResult]:        
        """
        Process an incoming message and create a summary.

        Args:
            channel: The channel to which the summary belongs
            category: The category of the note
            language: The language of the message
            message: The message content
            metadata: Optional dictionary containing additional metadata for the note
        """
        if self._setting.get_summarization_llm_provider() != "gemini":
            self._logger.error(f"Only Gemini models are supported.")
            return create_fallback_structure(message, language, channel, category)

        llm_model = self._setting.get_summarization_model()

        # determine if message needs to be chunked based on length and model limits
        if len(message) > self._setting.get_summarization_threshold():
            self._logger.info(f"Message exceeds threshold ({len(message)} > {self._setting.get_summarization_threshold()}), switching to advanced model...")
            llm_model = self._setting.get_summarization_advanced_model()

        self._logger.info(f"Processing message length {len(message)} using {llm_model}")

        try:
            title_prompt = produce_title_prompt(language, message)

            client = genai.Client()
            payload = f"{title_prompt}"
            response = client.models.generate_content(
                model=llm_model,
                contents=[payload]
            )
            title = response.text

            # must summarize if the message is a transcript
            if metadata and metadata["mode"]:
                transcript_prompt = produce_summarization_prompt(language, "transcript", message) 
                payload = f"{transcript_prompt}"
                response = client.models.generate_content(
                    model=llm_model,
                    contents=[payload]
                )
                message = response.text

            return process_response(message,
                title,
                language,
                channel,     
                category,
                metadata)

        except Exception as e:
            self._logger.error(f"Error summarizing text message: {e}")
            return create_fallback_structure(message, language, channel, category)
