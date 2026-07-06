from typing import Optional, Protocol
from pathlib import Path

class ITranscriberService(Protocol):
    """Protocol defining the transcriber interface."""

    def transcribe_youtube_video(self, youtube_url: str, language: Optional[str] = None) -> str:
        """
        Transcribe a YouTube video.

        Args:
            youtube_url: The URL of the YouTube video to transcribe
            language: The language of the video (optional)

        Returns:
            The transcribed text
        """
        ...

    def transcribe_audio_file(self, audio_path: Path, language: Optional[str] = None) -> str:
        """
        Transcribe an audio file.

        Args:
            audio_path: The path to the audio file to transcribe
            language: The language of the audio (optional)

        Returns:
            The transcribed text
        """
        ...
