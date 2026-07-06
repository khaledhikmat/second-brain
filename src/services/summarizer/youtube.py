import datetime
import requests
import re

from urllib.parse import urlparse, parse_qs
from typing import Any, Dict, Optional

from src.services.setting.typex import ISettingService
from src.services.logger.typex import ILoggerService
from src.services.typex import SummarizerResult
from src.services.summarizer.typex import ISummarizerService
from src.services.transcriber.typex import ITranscriberService

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
        ) -> SummarizerResult:        
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
            youtube_url = message.strip()

            # Extract video ID
            video_id = self._extract_video_id(youtube_url)
            self._logger.info(f"Processing YouTube video: {video_id}")

            # Get video metadata (title, etc.)
            video_info = self._get_video_info(video_id)
            self._logger.info(f"Video title: {video_info['title']}")

            # Try to get transcript from API first (existing captions)
            transcript = self._get_transcript_from_api(video_id)

            # If no transcript available, use Whisper API to transcribe audio
            if not transcript:
                self._logger.info("No captions found, attempting Whisper transcription...")
                try:
                    # Transcribe using the transcriber service
                    transcript = self._transcriber_service.transcribe_youtube_video(youtube_url, language)
                except Exception as ex:
                    self._logger.error(f"Whisper transcription failed: {ex}", exc_info=True)
                    return self._create_fallback_structure( 
                        message_text=f"Failed to transcribe YouTube video: {ex}",
                        language=language,
                        specified_title=video_info['title'],
                        specified_category=category
                    )

            return self._text_summarizer_service(
                channel, 
                transcript, 
                category=category,
                language=language, 
                specified_title=video_info['title'], 
                metadata={
                    "video_id": video_info['video_id'],
                    "url": video_info['url'],
                    "source": "youtube"
                }
            )

        except Exception as e:
            self._logger.error(f"Failed to process YouTube video: {e}", exc_info=True)
            return self._create_fallback_structure( 
                message_text=f"Failed to transcribe YouTube video: {ex}",
                language=language,
                specified_title=video_info['title'],
                specified_category=category
            )

    def _extract_video_id(self, url: str) -> str:
        """
        Extract video ID from YouTube URL.

        Args:
            url: YouTube URL

        Returns:
            Video ID

        Raises:
            ValueError: If URL is invalid or video ID cannot be extracted
        """
        # Handle different YouTube URL formats
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/v/)([\w-]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                return match.group(1)

        # Try parsing query parameters
        try:
            parsed = urlparse(url)
            if 'youtube.com' in parsed.netloc:
                query_params = parse_qs(parsed.query)
                if 'v' in query_params:
                    return query_params['v'][0]
        except Exception:
            pass

        raise ValueError(f"Could not extract video ID from URL: {url}")

    def _get_video_info(self, video_id: str) -> Dict[str, Any]:
        """
        Get video metadata (title, etc.) from YouTube.

        Args:
            video_id: YouTube video ID

        Returns:
            Dictionary with video metadata
        """
        try:
            # Fetch YouTube page and extract title from HTML
            url = f"https://www.youtube.com/watch?v={video_id}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            # Extract title from HTML (YouTube embeds it in the page title and meta tags)
            # Try to find the title in the HTML
            title_match = re.search(r'<title>([^<]+)</title>', response.text)
            if title_match:
                video_title = title_match.group(1)
                # Clean up the title (remove " - YouTube" suffix)
                video_title = video_title.replace(' - YouTube', '').strip()
            else:
                video_title = f"YouTube Video {video_id}"

            self._logger.info(f"Extracted video title: {video_title}")

            return {
                "title": video_title,
                "video_id": video_id,
                "url": url
            }
        except Exception as e:
            self._logger.warning(f"Could not fetch video metadata: {e}")
            return {
                "title": f"YouTube Video {video_id}",
                "video_id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}"
            }
        
    def _get_transcript_from_api(self, video_id: str) -> Optional[str]:
        """
        Get transcript using YouTube Transcript API.

        Args:
            video_id: YouTube video ID

        Returns:
            Transcript text or None if not available
        """
        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            self._logger.info(f"Fetching transcript for video: {video_id}")

            # Create API instance
            api = YouTubeTranscriptApi()

            # Try to get transcript list
            try:
                transcript_list = api.list(video_id)

                # Try to find transcript in preferred languages
                try:
                    transcript = transcript_list.find_transcript(self.transcript_languages)
                    transcript_data = transcript.fetch()
                    full_text = " ".join([entry.text for entry in transcript_data])
                    self._logger.info(f"Found transcript in {transcript.language} (length: {len(full_text)} chars)")
                    return full_text
                except Exception:
                    # Try English as fallback
                    self._logger.info(f"No transcript in preferred languages ({self.transcript_languages}), trying English...")
                    try:
                        transcript = transcript_list.find_transcript(['en'])
                        transcript_data = transcript.fetch()
                        full_text = " ".join([entry.text for entry in transcript_data])
                        self._logger.info(f"Found English transcript (length: {len(full_text)} chars)")
                        return full_text
                    except Exception:
                        # Try any available language
                        self._logger.info("No English transcript, trying any available language...")
                        try:
                            # Get first available transcript
                            transcript = transcript_list.find_generated_transcript([])
                            if not transcript:
                                transcript = transcript_list.find_manually_created_transcript([])
                            if transcript:
                                transcript_data = transcript.fetch()
                                full_text = " ".join([entry.text for entry in transcript_data])
                                self._logger.info(f"Found transcript in {transcript.language} (length: {len(full_text)} chars)")
                                return full_text
                        except Exception as e3:
                            self._logger.info(f"No transcript available: {e3}")
                            return None

            except Exception as e:
                self._logger.info(f"Could not retrieve transcripts: {e}")
                return None

        except Exception as e:
            self._logger.error(f"Error fetching transcript: {e}", exc_info=True)
            return None

    def _create_fallback_structure(
        self,
        message_text: str,
        language: str,
        specified_title: Optional[str] = None,
        specified_category: Optional[str] = None
    ) -> SummarizerResult:
        """Create a basic structure when Claude processing fails."""
        return SummarizerResult(
            title=specified_title or f"Note - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            category=specified_category or "Jots",
            tags=["unprocessed"],
            concepts=[],
            entities={"people": [], "places": [], "terms": []},
            summary=message_text[:200] + ("..." if len(message_text) > 200 else ""),
            wikilinks=[],
            content=message_text,
            processed_at=datetime.now().isoformat(),
            language=language,
            fallback=True
        )


