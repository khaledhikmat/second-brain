from typing import Any, Dict, Optional, List
from datetime import datetime

from google import genai
from google.genai import types

from services.setting.typex import ISettingService
from services.logger.typex import ILoggerService
from services.summarizer.typex import SummarizerResult, produce_summarization_prompt, process_response, create_fallback_structure

class GeminiTextSummarizerService:
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
        ) -> Optional [SummarizerResult]:        
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
        llm_model = self._setting.get_summarization_model()

        # determine if message needs to be chunked based on length and model limits
        if len(message) > self._setting.get_summarization_threshold():
            self._logger.info(f"Message exceeds threshold ({len(message)} > {self._setting.get_summarization_threshold()}), switching to advanced model...")
            llm_model = self._setting.get_summarization_advanced_model()

        self._logger.info(f"Processing message length {len(message)} using {llm_model}")

        skip_summarization = False
        if category and category.lower() in ["sayings", "poetry"]:
            skip_summarization = True

        prompt = produce_summarization_prompt(category, language, message, skip_summarization)
        self._logger.debug(f"Prompt: {prompt}")

        try:
            response_text = ""
            if self._setting.get_summarization_llm_provider() == "claude":
                response_text = self._execute_claude_model(llm_model, prompt, message)
            else:
                response_text = self._execute_gemini_model(llm_model, prompt, message)

            return process_response(message,
                response_text,
                channel,     
                language,
                category,
                specified_title)

        except Exception as e:
            self._logger.error(f"Error summarizing text message: {e}")
            return create_fallback_structure(message, language, specified_title, category)

    def _execute_gemini_model(self, llm_model: str, prompt: str, message: str):
        # Initialize the Gemini Client 
        # (Make sure os.environ["GEMINI_API_KEY"] is set)
        client = genai.Client()

        payload = f"{prompt}\n\nTranscript Content:\n{message}"
        
        response = client.models.generate_content(
            model=llm_model,
            contents=[payload]
        )

        return response.text

    def _execute_claude_model(self, llm_model: str, prompt: str, message: str):
        return NotImplementedError("Claude summarizer is not implemented yet.")
