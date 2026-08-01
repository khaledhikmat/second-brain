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
            message: Youtube URL
            metadata: Optional dictionary containing additional metadata for the note
        """
        if self._setting.get_summarization_llm_provider() != "gemini":
            self._logger.error(f"Only Gemini models are supported.")
            return create_fallback_structure(message, language, channel, category)

        try:
            url = message.strip()
            self._logger.info(f"Analyzing video: {url}")
            video_id = self._extract_video_id(url)

            # Normalize URL to standard YouTube format for Gemini API
            normalized_url = f"https://www.youtube.com/watch?v={video_id}"
            self._logger.info(f"Normalized URL: {normalized_url}")
            
            metadata = {
                "source": "youtube",
                "reference": url
            }

            # Path A: Check for Text Transcripts first
            self._logger.info("━━━ PATH A: YouTube Transcript API ━━━")
            transcript_text = self._fetch_transcript_text(video_id)

            if transcript_text:
                self._logger.info(f"✓ Path A succeeded: Transcript available ({len(transcript_text)} chars)")
                if self._text_summarizer_service is None:
                    self._logger.error("Text summarizer is not available.")
                    return create_fallback_structure(message, language, channel, category)

                metadata["mode"] = "transcript" 

                # Route to text summarizer
                self._logger.info("➔ Routing transcript to text summarizer...")
                return await self._text_summarizer_service.summarize(channel, category, language, transcript_text, metadata)
            else:
                self._logger.info("✗ Path A failed: No transcript available, trying fallback paths...")

            # Path B: Try Gemini multimodal (if enabled and video is short enough)
            # Path C: Fall back to Whisper transcription if multimodal fails

            self._logger.info("━━━ PATH B: Gemini Multimodal ━━━")
            gemini_response_text = None
            try:
                prompt = produce_summarization_prompt(language, "youtube")
                self._logger.debug(f"Youtube prompt: {prompt}")

                client = genai.Client()
                self._logger.info("➔ Evaluating video duration for Gemini multimodal...")
                duration_seconds = self._get_video_duration(client, normalized_url)
                duration_hours = duration_seconds / 3600
                self._logger.info(f"   Video duration: {duration_hours:.2f} hours")

                # Enforce duration guardrails
                gemini_model = self._setting.get_summarization_model()
                if duration_hours <= 1.0:
                    gemini_model = self._setting.get_summarization_model()
                elif duration_hours > 1.0 and duration_hours <= 2.0:
                    gemini_model = self._setting.get_summarization_advanced_model()
                else:
                    self._logger.warning(f"✗ Path B skipped: Video too long ({duration_hours:.2f} hours)")
                    raise Exception("Video too long for Gemini multimodal")

                self._logger.info(f"➔ Sending video to {gemini_model}...")
                video_part = types.Part.from_uri(file_uri=normalized_url, mime_type="video/mp4")
                response = client.models.generate_content(
                    model=gemini_model,
                    contents=[video_part, prompt]
                )
                gemini_response_text = response.text
                self._logger.info(f"✓ Path B succeeded: Gemini multimodal completed ({len(gemini_response_text)} chars)")

            except Exception as e:
                self._logger.warning(f"✗ Path B failed: {type(e).__name__}: {str(e)[:100]}")
                self._logger.info("━━━ PATH C: Whisper Transcription ━━━")

                # Path C: Use Whisper as fallback
                if self._transcriber_service is None:
                    self._logger.error("✗ Path C failed: Whisper transcriber is not available")
                    return create_fallback_structure(message, language, channel, category)

                try:
                    # Transcribe with Whisper (let it auto-detect language for reliability)
                    # Note: Passing None for language to avoid invalid language code errors
                    self._logger.info("➔ Downloading and transcribing audio with Whisper...")
                    whisper_transcript = self._transcriber_service.transcribe_youtube_video(url, None)

                    if whisper_transcript:
                        self._logger.info(f"✓ Path C succeeded: Whisper transcription completed ({len(whisper_transcript)} chars)")

                        metadata["mode"] = "whisper" 

                        # Route to text summarizer
                        self._logger.info("➔ Routing transcript to text summarizer...")
                        return await self._text_summarizer_service.summarize(channel, category, language, whisper_transcript, metadata)
                    else:
                        self._logger.error("✗ Path C failed: Whisper returned empty result")
                        return create_fallback_structure(message, language, channel, category)

                except Exception as whisper_error:
                    self._logger.error(f"✗ Path C failed: {type(whisper_error).__name__}: {str(whisper_error)[:100]}")
                    return create_fallback_structure(message, language, channel, category)

            # If Gemini multimodal succeeded, process the response
            if gemini_response_text:
                self._logger.info("➔ Processing Gemini multimodal response...")
                # produce consistent titles across all sources
                title_summary = await self._text_summarizer_service.summarize(channel, category, language, gemini_response_text)

                metadata["mode"] = "multimodal" 

                return process_response(gemini_response_text,
                    title_summary.title,
                    language,
                    channel,
                    category,
                    metadata)
            
        except Exception as e:
            self._logger.error(f"Error processing message with Gemini: {e}")
            return create_fallback_structure(message, language, channel, category)

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
        token_check = client.models.count_tokens(
            model=self._setting.get_summarization_model(),
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
            self._logger.debug(f"Fetching transcript for video: {video_id}")

            # Create API instance
            api = YouTubeTranscriptApi()

            # First, list available transcripts to log them
            try:
                transcript_list = api.list(video_id)
                available_langs = [f"{t.language_code}{'(auto)' if t.is_generated else ''}"
                                  for t in transcript_list]
                self._logger.info(f"Available transcripts: {', '.join(available_langs)}")
            except Exception as list_error:
                self._logger.debug(f"Could not list transcripts: {list_error}")

            # Try to fetch transcript, prioritizing Arabic and English
            try:
                self._logger.debug("Trying to fetch ar/en transcript...")
                fetched = api.fetch(video_id, languages=['ar', 'en'])
                selected_language = fetched.language_code
                self._logger.info(f"Found preferred transcript: {selected_language}")
            except NoTranscriptFound:
                # Fall back to any available language
                try:
                    self._logger.debug("Trying to fetch any available transcript...")
                    fetched = api.fetch(video_id, languages=['en'])  # Default to English
                    selected_language = fetched.language_code
                    self._logger.info(f"Found transcript: {selected_language}")
                except NoTranscriptFound:
                    self._logger.warning(f"No transcripts found for video {video_id}")
                    return None

            # Convert transcript snippets to text
            transcript_text = " ".join([snippet.text for snippet in fetched])
            self._logger.info(f"✓ Transcript fetched successfully ({len(transcript_text)} chars, lang={selected_language})")
            return transcript_text

        except TranscriptsDisabled:
            self._logger.warning(f"Transcripts are disabled for video {video_id}")
            return None
        except NoTranscriptFound:
            self._logger.warning(f"No transcripts found for video {video_id}")
            return None
        except Exception as e:
            self._logger.error(f"Unexpected error fetching transcript: {e}", exp=e)
            return None

