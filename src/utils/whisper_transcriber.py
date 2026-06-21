"""OpenAI Whisper transcription utility for YouTube videos."""

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

import yt_dlp
from pydub import AudioSegment
from openai import OpenAI

logger = logging.getLogger(__name__)


class WhisperTranscriber:
    """Transcribe audio using OpenAI Whisper API."""

    def __init__(self, api_key: str):
        """
        Initialize Whisper transcriber.

        Args:
            api_key: OpenAI API key
        """
        self.client = OpenAI(api_key=api_key)
        logger.info("WhisperTranscriber initialized (using OpenAI Whisper API)")

    def transcribe_youtube_video(self, youtube_url: str, language: Optional[str] = None) -> str:
        """
        Transcribe a YouTube video using OpenAI Whisper API.

        Downloads audio from YouTube using yt-dlp, splits into chunks,
        and transcribes each chunk with Whisper API.

        Args:
            youtube_url: YouTube video URL
            language: Optional language code for transcription (e.g., 'en', 'ar')

        Returns:
            Transcribed text

        Raises:
            RuntimeError: If transcription fails
        """
        try:
            logger.info(f"Starting YouTube transcription for: {youtube_url}")

            # Use temporary directory for all intermediate files
            # Automatically cleaned up when exiting the 'with' block
            with tempfile.TemporaryDirectory(prefix="transcribe_") as work_dir:
                # Download audio to temp directory
                audio_path = os.path.join(work_dir, 'audio')
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                    'outtmpl': f'{audio_path}.%(ext)s',
                    'quiet': True,
                    'no_warnings': True,
                    # Bot detection bypass options
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    'referer': 'https://www.youtube.com/',
                    'extractor_args': {
                        'youtube': {
                            'player_client': ['android', 'web'],
                            'player_skip': ['webpage', 'configs'],
                        }
                    },
                }

                logger.info("Downloading audio from YouTube...")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([youtube_url])

                # Load the downloaded audio file
                audio_file_path = f"{audio_path}.mp3"

                if not os.path.exists(audio_file_path):
                    raise RuntimeError(f"Audio file not found: {audio_file_path}")

                file_size_mb = os.path.getsize(audio_file_path) / (1024 * 1024)
                logger.info(f"✓ Audio downloaded ({file_size_mb:.2f} MB)")

                # Split audio into 10-minute chunks (Whisper API has 25MB limit)
                logger.info("Splitting audio into chunks...")
                audio = AudioSegment.from_mp3(audio_file_path)
                chunk_length_ms = 10 * 60 * 1000  # 10 minutes in milliseconds

                chunks = []
                for i in range(0, len(audio), chunk_length_ms):
                    chunk = audio[i:i + chunk_length_ms]
                    chunk_filename = os.path.join(work_dir, f"chunk_{i//chunk_length_ms}.mp3")
                    chunk.export(chunk_filename, format="mp3")
                    chunks.append(chunk_filename)

                logger.info(f"✓ Split into {len(chunks)} chunks")

                # Transcribe each chunk
                full_transcript = ""
                for idx, chunk_file in enumerate(chunks, 1):
                    logger.info(f"Transcribing chunk {idx}/{len(chunks)}...")

                    with open(chunk_file, "rb") as audio_file:
                        # Prepare transcription parameters
                        transcribe_params = {
                            "model": "whisper-1",
                            "file": audio_file,
                        }

                        # Add language if specified
                        if language:
                            transcribe_params["language"] = language

                        transcript = self.client.audio.transcriptions.create(**transcribe_params)
                        full_transcript += transcript.text + "\n"

                logger.info(f"✓ Transcription completed ({len(full_transcript)} chars)")
                return full_transcript.strip()

        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            if "Sign in to confirm you're not a bot" in error_msg or "bot" in error_msg.lower():
                logger.error(f"YouTube blocked the download (bot detection): {e}")
                raise RuntimeError(
                    "YouTube blocked the download due to bot detection. "
                    "This video may not have captions available via YouTube Transcript API. "
                    "Try a different video or contact support to enable cookie authentication."
                )
            else:
                logger.error(f"Failed to download YouTube video: {e}", exc_info=True)
                raise RuntimeError(f"YouTube download failed: {e}")
        except Exception as e:
            logger.error(f"Failed to transcribe YouTube video: {e}", exc_info=True)
            raise RuntimeError(f"YouTube transcription failed: {e}")

    def transcribe_audio_file(self, audio_path: Path, language: Optional[str] = None) -> str:
        """
        Transcribe an audio file using Whisper API.

        Args:
            audio_path: Path to audio file
            language: Optional language code

        Returns:
            Transcribed text

        Raises:
            RuntimeError: If transcription fails
        """
        try:
            logger.info(f"Transcribing audio file: {audio_path}")

            with open(audio_path, "rb") as audio_file:
                transcribe_params = {
                    "model": "whisper-1",
                    "file": audio_file,
                }

                if language:
                    transcribe_params["language"] = language

                transcript = self.client.audio.transcriptions.create(**transcribe_params)

            return transcript.text

        except Exception as e:
            logger.error(f"Failed to transcribe audio file: {e}", exc_info=True)
            raise RuntimeError(f"Audio transcription failed: {e}")
