import re

from typing import Any, Dict, Optional

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
        ) -> Optional[SummarizerResult]:

        if self._setting.get_summarization_llm_provider() != "gemini":
            self._logger.error("Only Gemini models are supported.")
            return create_fallback_structure(message, language, channel, category)

        try:
            url = message.strip()
            self._logger.info(f"Analyzing video: {url}")
            video_id = self._extract_video_id(url)
            normalized_url = f"https://www.youtube.com/watch?v={video_id}"
            self._logger.info(f"Normalized URL: {normalized_url}")

            metadata = {"source": "youtube", "reference": url}

            # Path A: injected transcriber service (caller controls which one)
            self._logger.info(f"━━━ PATH A: {type(self._transcriber_service).__name__} ━━━")
            transcript_text = None
            try:
                transcript_text = self._transcriber_service.transcribe_youtube_video(url, language)
            except Exception as e:
                self._logger.warning(f"✗ Path A failed: {type(e).__name__}: {str(e)[:120]}")

            if transcript_text:
                self._logger.info(f"✓ Path A succeeded ({len(transcript_text)} chars)")
                metadata["mode"] = "transcript"
                self._logger.info("➔ Routing transcript to text summarizer...")
                return await self._text_summarizer_service.summarize(channel, category, language, transcript_text, metadata)

            self._logger.info("✗ Path A: no transcript, falling back to Gemini multimodal...")

            # Path B: Gemini multimodal
            self._logger.info("━━━ PATH B: Gemini Multimodal ━━━")
            prompt = produce_summarization_prompt(language, "youtube")
            self._logger.debug(f"Youtube prompt: {prompt}")

            client = genai.Client()
            self._logger.info("➔ Evaluating video duration for Gemini multimodal...")
            duration_seconds = self._get_video_duration(client, normalized_url)
            duration_hours = duration_seconds / 3600
            self._logger.info(f"   Video duration: {duration_hours:.2f} hours")

            if duration_hours <= 1.0:
                gemini_model = self._setting.get_summarization_model()
            elif duration_hours <= 2.0:
                gemini_model = self._setting.get_summarization_advanced_model()
            else:
                self._logger.warning(f"✗ Path B skipped: video too long ({duration_hours:.2f} hours)")
                return create_fallback_structure(message, language, channel, category)

            self._logger.info(f"➔ Sending video to {gemini_model}...")
            video_part = types.Part.from_uri(file_uri=normalized_url, mime_type="video/mp4")
            response = client.models.generate_content(
                model=gemini_model,
                contents=[video_part, prompt]
            )
            gemini_response_text = response.text
            self._logger.info(f"✓ Path B succeeded ({len(gemini_response_text)} chars)")

            self._logger.info("➔ Processing Gemini multimodal response...")
            # produce consistent titles across all sources
            title_summary = await self._text_summarizer_service.summarize(channel, category, language, gemini_response_text)
            metadata["mode"] = "multimodal"
            return process_response(gemini_response_text, title_summary.title, language, channel, category, metadata)

        except Exception as e:
            self._logger.warning(f"✗ Path B failed: {type(e).__name__}: {str(e)[:120]}")
            raise ValueError(f"Error processing YouTube video with Gemini: {type(e).__name__}: {str(e)[:120]}")

    def _extract_video_id(self, url: str) -> str:
        match = re.search(r'(?:v=|\/v\/|youtu\.be\/|\/embed\/)([a-zA-Z0-9_-]{11})', url)
        if not match:
            raise ValueError("Invalid YouTube URL format.")
        return match.group(1)

    def _get_video_duration(self, client, video_url: str) -> float:
        video_part = types.Part.from_uri(file_uri=video_url, mime_type="video/mp4")
        token_check = client.models.count_tokens(
            model=self._setting.get_summarization_model(),
            contents=[video_part]
        )
        # ~295 tokens per second of video
        return token_check.total_tokens / 295

