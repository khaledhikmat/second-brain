import re
from typing import Optional
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

from services.setting.typex import ISettingService
from services.logger.typex import ILoggerService


class YouTubeApiTranscriberService:
    """Fetch transcript from YouTube's native caption API (free, but blocked on cloud IPs)."""

    def __init__(self, setting: ISettingService, logger: ILoggerService):
        self._setting = setting
        self._logger = logger

    def transcribe_youtube_video(self, youtube_url: str, language: Optional[str] = None) -> Optional[str]:
        video_id = self._extract_video_id(youtube_url)
        return self._fetch_transcript(video_id)

    def transcribe_audio_file(self, audio_path: Path, language: Optional[str] = None) -> str:
        raise NotImplementedError("YouTubeApiTranscriberService only supports YouTube URLs.")

    def _extract_video_id(self, url: str) -> str:
        match = re.search(r'(?:v=|\/v\/|youtu\.be\/|\/embed\/)([a-zA-Z0-9_-]{11})', url)
        if not match:
            raise ValueError("Invalid YouTube URL format.")
        return match.group(1)

    def _fetch_transcript(self, video_id: str) -> Optional[str]:
        try:
            self._logger.debug(f"Fetching transcript for video: {video_id}")
            api = YouTubeTranscriptApi()

            try:
                transcript_list = api.list(video_id)
                available = [f"{t.language_code}{'(auto)' if t.is_generated else ''}" for t in transcript_list]
                self._logger.info(f"Available transcripts: {', '.join(available)}")
            except Exception as e:
                self._logger.debug(f"Could not list transcripts: {e}")

            try:
                self._logger.debug("Trying to fetch ar/en transcript...")
                fetched = api.fetch(video_id, languages=['ar', 'en'])
            except NoTranscriptFound:
                try:
                    self._logger.debug("Falling back to any available transcript...")
                    fetched = api.fetch(video_id)
                except NoTranscriptFound:
                    self._logger.warning(f"No transcripts found for video {video_id}")
                    return None

            text = " ".join([s.text for s in fetched])
            self._logger.info(f"✓ Transcript fetched ({len(text)} chars, lang={fetched.language_code})")
            return text

        except TranscriptsDisabled:
            self._logger.warning(f"Transcripts disabled for video {video_id}")
            return None
        except Exception as e:
            self._logger.error(f"Unexpected error fetching transcript: {e}")
            return None
