import os
import requests
import re

from typing import Any, Dict, Optional

from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from google import genai
from google.genai import types

from services.setting.typex import ISettingService
from services.logger.typex import ILoggerService
from services.transcriber.typex import ITranscriberService
from services.summarizer.typex import ISummarizerService, SummarizerResult, produce_summarization_prompt, process_response, create_fallback_structure

class YoutubeSummarizerService:
    def __init__(self, setting: ISettingService, logger: ILoggerService, transcriber_service: ITranscriberService, text_summarizer_service: ISummarizerService):
        self._setting = setting
        self._logger = logger
        self._transcriber_service = transcriber_service
        self._text_summarizer_service = text_summarizer_service

    async def summarize(
            self,
            channel: str,
            message: str,
            category: str,
            language: str = None,
            title: Optional[str] = None,
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
        try:
            # Youtube only works with Gemini models because Youtube is involved
            if self._setting.get_summarization_llm_provider() != "gemini":
                self._logger.error(f"Gemini model is not available.")
                return create_fallback_structure(message, language, title, category)

            client = genai.Client()
            skip_summarization = False
            if category and category.lower() in ["sayings", "poetry"]:
                skip_summarization = True

            prompt = produce_summarization_prompt(category, language, message, skip_summarization)
            self._logger.debug(f"Prompt: {prompt}")

            url = message.strip()

            self._logger.info(f"Analyzing video: {url}")
            video_id = self._extract_video_id(url)
            
            # Path A: Check for Text Transcripts first
            self._logger.info("➔ Evaluating video transcripts...")
            transcript_text = self._fetch_transcript_text(video_id)
            
            if transcript_text and self._text_summarizer_service is None:
                self._logger.error(f"Text summarizer is not available.")
                return create_fallback_structure(message, language, title, category)

            if transcript_text and self._text_summarizer_service is not None:
                # route to the text summarizer
                return self._text_summarizer_service(channel, transcript_text, category, language, title, metadata)

            # Path B: No Transcript available. We must fall back to multimodal rules.
            self._logger.info("➔ No transcript available. Evaluating video duration...")
            try:
                duration_seconds = self._get_video_duration(client, url)
                duration_hours = duration_seconds / 3600
                self._logger.info(f"   Estimated Video Length: {duration_hours:.2f} hours")
            except Exception as e:
                self._logger.error(f"Routing Error: Failed to evaluate video duration. Details: {e}")
                return create_fallback_structure(message, language, title, category)

            self._logger.info(f"Video duration: {duration_hours}")
            # Enforce duration guardrails
            if duration_hours <= 1.0:
                self._logger.info(f"➔ Under 1 hour. Routing multimodal payload to {self._setting.get_summarization_model()}...")
                video_part = types.Part.from_uri(file_uri=url, mime_type="video/mp4")
                response = client.models.generate_content(
                    model=self._setting.get_summarization_model(),
                    contents=[video_part, prompt]
                )
                return process_response(message,
                    response.text,
                    channel,     
                    language,
                    category,
                    title,
                    {
                        "source": "youtube",
                        "reference": url
                    })
                
            elif duration_hours <= 2.0:
                self._logger.info(f"➔ Between 1 and 2 hours. Routing heavy multimodal payload to flagship {self._setting.get_summarization_advanced_model()}..")
                video_part = types.Part.from_uri(file_uri=url, mime_type="video/mp4")
                response = client.models.generate_content(
                    model=self._setting.get_summarization_advanced_model(),
                    contents=[video_part, prompt]
                )
                return process_response(message,
                    response.text,
                    channel,     
                    language,
                    category,
                    title,
                    {
                        "source": "youtube",
                        "reference": url
                    })
                
            else:
                self._logger.error(f"Execution Failed: Video is {duration_hours:.2f} hours long with no available text transcript.")
                return create_fallback_structure(message, language, title, category)
        except Exception as e:
            self._logger.error(f"Error processing message with Gemini: {e}")
            return create_fallback_structure(message, language, title, category)

    def _extract_video_id(self, url: str) -> str:
        """Extracts the 11-character video ID from various YouTube URL formats."""
        pattern = r'(?:v=|\/v\/|youtu\.be\/|\/embed\/)([a-zA-Z0-9_-]{11})'
        match = re.search(pattern, url)
        if not match:
            raise ValueError("Invalid YouTube URL format.")
        return match.group(1)

    def _get_video_duration(self, client, video_url: str) -> float:
        """
        Leverages Gemini's fast, free count_tokens metadata check to 
        infer total video length without needing a YouTube Data API Key.
        """
        video_part = types.Part.from_uri(file_uri=video_url, mime_type="video/mp4")
        token_check = client.count_tokens(
            model=self._setting.get_summarization_gemini_model(),
            contents=[video_part]
        )
        # Baseline: Video processing consumes roughly 295 tokens per second
        estimated_seconds = token_check.total_tokens / 295
        return estimated_seconds

    def _fetch_transcript_text(self, video_id: str) -> str:
        """
        Attempts to fetch a transcript, prioritizing arabic ('ar') or english ('en').
        Returns the raw string text if found, otherwise returns None.
        """
        try:
            # Retrieve transcript list to check available languages
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Prioritize Arabic, then English, fallback to auto-generated versions
            try:
                transcript = transcript_list.find_transcript(['ar', 'en'])
            except NoTranscriptFound:
                # If preferred languages aren't found, pick the absolute first available track
                transcript = next(iter(transcript_list))
                
            data = transcript.fetch()
            return " ".join([entry['text'] for entry in data])
            
        except (TranscriptsDisabled, NoTranscriptFound, Exception):
            return None

