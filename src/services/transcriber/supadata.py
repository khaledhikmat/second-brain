from typing import Optional
from pathlib import Path

import requests

from services.setting.typex import ISettingService
from services.logger.typex import ILoggerService


class SupadataTranscriberService:
    """Fetch YouTube transcript via Supadata API (cloud-friendly, works from Railway/AWS/GCP)."""

    _ENDPOINT = "https://api.supadata.ai/v1/youtube/transcript"

    def __init__(self, setting: ISettingService, logger: ILoggerService):
        self._setting = setting
        self._logger = logger

    def transcribe_youtube_video(self, youtube_url: str, language: Optional[str] = None) -> Optional[str]:
        api_key = self._setting.get_transcriber_supadata_api_key()
        if not api_key:
            raise RuntimeError("TRANSCRIBER_SUPADATA_API_KEY is not configured.")

        self._logger.info(f"Fetching transcript via Supadata for: {youtube_url}")
        response = requests.get(
            self._ENDPOINT,
            params={"url": youtube_url, "text": "true"},
            headers={"x-api-key": api_key},
            timeout=30,
        )

        if response.status_code == 404:
            self._logger.warning("Supadata: no transcript available for this video.")
            return None

        response.raise_for_status()

        content = response.json().get("content", "")
        if not content:
            self._logger.warning("Supadata returned empty transcript content.")
            return None

        self._logger.info(f"✓ Supadata transcript fetched ({len(content)} chars)")
        return content

    def transcribe_audio_file(self, audio_path: Path, language: Optional[str] = None) -> str:
        raise NotImplementedError("SupadataTranscriberService only supports YouTube URLs.")
