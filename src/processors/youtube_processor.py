"""YouTube video transcript processor."""

import logging
import re
from typing import Optional, List
from urllib.parse import urlparse, parse_qs

from ..config import (
    YOUTUBE_TRANSCRIPT_LANGUAGES,
    YOUTUBE_SUMMARIZE_THRESHOLD,
    YOUTUBE_CHUNK_SIZE,
    OPENAI_API_KEY
)
from ..utils.whisper_transcriber import WhisperTranscriber

logger = logging.getLogger(__name__)


class YouTubeProcessor:
    """Process YouTube videos to extract transcripts."""

    def __init__(self, claude_processor):
        """
        Initialize YouTube processor.

        Args:
            claude_processor: Claude AI processor for summarization
        """
        self.claude_processor = claude_processor
        self.transcript_languages = YOUTUBE_TRANSCRIPT_LANGUAGES
        self.summarize_threshold = YOUTUBE_SUMMARIZE_THRESHOLD
        self.chunk_size = YOUTUBE_CHUNK_SIZE

        # Initialize Whisper transcriber for audio transcription
        if not OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY is required for YouTube transcription"
            )

        self.whisper_transcriber = WhisperTranscriber(api_key=OPENAI_API_KEY)
        logger.info("OpenAI Whisper API initialized for transcription")
        logger.info("YouTube processor initialized")

    @staticmethod
    def is_youtube_url(text: str) -> bool:
        """
        Check if text contains a YouTube URL.

        Args:
            text: Text to check

        Returns:
            True if text contains a YouTube URL
        """
        youtube_patterns = [
            r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+',
            r'(?:https?://)?(?:www\.)?youtu\.be/[\w-]+',
            r'(?:https?://)?(?:www\.)?youtube\.com/embed/[\w-]+',
            r'(?:https?://)?(?:www\.)?youtube\.com/v/[\w-]+',
        ]

        for pattern in youtube_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        return False

    def get_video_info(self, video_id: str) -> dict:
        """
        Get video metadata (title, etc.) from YouTube.

        Args:
            video_id: YouTube video ID

        Returns:
            Dictionary with video metadata
        """
        try:
            import requests
            import re

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

            logger.info(f"Extracted video title: {video_title}")

            return {
                "title": video_title,
                "video_id": video_id,
                "url": url
            }
        except Exception as e:
            logger.warning(f"Could not fetch video metadata: {e}")
            return {
                "title": f"YouTube Video {video_id}",
                "video_id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}"
            }

    @staticmethod
    def extract_video_id(url: str) -> str:
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

    def get_transcript_from_api(self, video_id: str) -> Optional[str]:
        """
        Get transcript using YouTube Transcript API.

        Args:
            video_id: YouTube video ID

        Returns:
            Transcript text or None if not available
        """
        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            logger.info(f"Fetching transcript for video: {video_id}")

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
                    logger.info(f"Found transcript in {transcript.language} (length: {len(full_text)} chars)")
                    return full_text
                except Exception:
                    # Try English as fallback
                    logger.info(f"No transcript in preferred languages ({self.transcript_languages}), trying English...")
                    try:
                        transcript = transcript_list.find_transcript(['en'])
                        transcript_data = transcript.fetch()
                        full_text = " ".join([entry.text for entry in transcript_data])
                        logger.info(f"Found English transcript (length: {len(full_text)} chars)")
                        return full_text
                    except Exception:
                        # Try any available language
                        logger.info("No English transcript, trying any available language...")
                        try:
                            # Get first available transcript
                            transcript = transcript_list.find_generated_transcript([])
                            if not transcript:
                                transcript = transcript_list.find_manually_created_transcript([])
                            if transcript:
                                transcript_data = transcript.fetch()
                                full_text = " ".join([entry.text for entry in transcript_data])
                                logger.info(f"Found transcript in {transcript.language} (length: {len(full_text)} chars)")
                                return full_text
                        except Exception as e3:
                            logger.info(f"No transcript available: {e3}")
                            return None

            except Exception as e:
                logger.info(f"Could not retrieve transcripts: {e}")
                return None

        except Exception as e:
            logger.error(f"Error fetching transcript: {e}", exc_info=True)
            return None

    def get_transcript_with_whisper(self, youtube_url: str, language: Optional[str] = None) -> str:
        """
        Get transcript using OpenAI Whisper API.

        Downloads audio with yt-dlp and transcribes with Whisper API.

        Args:
            youtube_url: YouTube video URL
            language: Optional language code (e.g., 'en', 'ar')

        Returns:
            Transcribed text

        Raises:
            RuntimeError: If transcription fails
        """
        logger.info("No captions available, using OpenAI Whisper API for transcription...")

        try:
            transcript = self.whisper_transcriber.transcribe_youtube_video(youtube_url, language=language)
            logger.info(f"✓ Whisper transcription completed (length: {len(transcript)} chars)")
            return transcript

        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}", exc_info=True)
            raise RuntimeError(f"Failed to transcribe video with Whisper API: {e}")

    def _split_transcript_into_chunks(self, transcript: str, chunk_size: int = 40000) -> List[str]:
        """
        Split a long transcript into manageable chunks.

        Args:
            transcript: Full transcript text
            chunk_size: Maximum characters per chunk (default: 40k chars ~10k tokens)

        Returns:
            List of transcript chunks
        """
        if len(transcript) <= chunk_size:
            return [transcript]

        chunks = []
        words = transcript.split()
        current_chunk = []
        current_length = 0

        for word in words:
            word_length = len(word) + 1  # +1 for space

            if current_length + word_length > chunk_size and current_chunk:
                # Save current chunk and start new one
                chunks.append(' '.join(current_chunk))
                current_chunk = [word]
                current_length = word_length
            else:
                current_chunk.append(word)
                current_length += word_length

        # Add final chunk
        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks

    def _summarize_single_chunk(self, chunk: str, lang_name: str, chunk_num: int = None, total_chunks: int = None) -> str:
        """
        Summarize a single chunk of transcript.

        Args:
            chunk: Transcript chunk to summarize
            lang_name: Language name for the summary
            chunk_num: Current chunk number (for logging)
            total_chunks: Total number of chunks (for logging)

        Returns:
            Summarized text
        """
        chunk_info = f" (chunk {chunk_num}/{total_chunks})" if chunk_num and total_chunks else ""
        logger.info(f"Summarizing transcript chunk{chunk_info} (length: {len(chunk)} chars)")

        prompt = f"""Please create a comprehensive summary of this video transcript{' section' if chunk_num else ''}.

IMPORTANT: The transcript is in {lang_name}. Your summary MUST be in {lang_name} as well.

Extract and organize:
1. Main topics and themes
2. Key points and takeaways
3. Important facts, quotes, or insights
4. Any actionable items or recommendations

Present the summary in a structured format that would work well as a note.
Write your entire response in {lang_name}.

Transcript:
{chunk}
"""

        from anthropic import Anthropic
        client = Anthropic(api_key=self.claude_processor.client.api_key)

        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return message.content[0].text.strip()

    def summarize_transcript(self, transcript: str) -> str:
        """
        Summarize a long transcript using Claude.

        Uses different strategies based on transcript length:
        - < 150k chars: Direct summarization (fits in Claude's context window)
        - >= 150k chars: Chunked summarization with map-reduce approach

        Args:
            transcript: Full transcript text

        Returns:
            Summarized text suitable for note creation
        """
        logger.info(f"Summarizing transcript (length: {len(transcript)} chars, ~{len(transcript)//4} tokens)")

        # Detect language from transcript to preserve it in summary
        from src.utils.language_detector import detect_language
        detected_lang = detect_language(transcript[:5000])
        lang_name = "Arabic" if detected_lang == "ar" else "English" if detected_lang == "en" else "the original language"

        logger.info(f"Detected transcript language: {detected_lang} ({lang_name})")

        try:
            # Strategy 1: For transcripts < 150k chars, summarize directly
            # (Claude Sonnet 4 has 200k token context = ~600k-800k chars)
            if len(transcript) < 150000:
                logger.info("Using direct summarization (transcript fits in context window)")
                return self._summarize_single_chunk(transcript, lang_name)

            # Strategy 2: For very long transcripts, use map-reduce chunking
            logger.info("Using chunked summarization for very long transcript")
            chunks = self._split_transcript_into_chunks(transcript, chunk_size=40000)
            logger.info(f"Split transcript into {len(chunks)} chunks")

            # Summarize each chunk
            chunk_summaries = []
            for i, chunk in enumerate(chunks, 1):
                chunk_summary = self._summarize_single_chunk(chunk, lang_name, i, len(chunks))
                chunk_summaries.append(chunk_summary)

            # If we have multiple chunk summaries, combine them into final summary
            if len(chunk_summaries) > 1:
                logger.info(f"Combining {len(chunk_summaries)} chunk summaries into final summary")

                combined_text = "\n\n".join([
                    f"Section {i}:\n{summary}"
                    for i, summary in enumerate(chunk_summaries, 1)
                ])

                # Create final combined summary
                final_prompt = f"""Please create a comprehensive final summary by combining these section summaries from a long video.

IMPORTANT: The content is in {lang_name}. Your final summary MUST be in {lang_name} as well.

Combine and organize:
1. Main topics and themes across all sections
2. Key points and takeaways
3. Important facts, quotes, or insights
4. Any actionable items or recommendations

Remove redundancy and create a cohesive, well-structured summary.
Write your entire response in {lang_name}.

Section Summaries:
{combined_text}
"""

                from anthropic import Anthropic
                client = Anthropic(api_key=self.claude_processor.client.api_key)

                message = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=8192,  # Larger output for combined summary
                    messages=[
                        {"role": "user", "content": final_prompt}
                    ]
                )

                final_summary = message.content[0].text.strip()
                logger.info(f"Final combined summary created (length: {len(final_summary)} chars)")
                return final_summary
            else:
                # Only one chunk, return its summary directly
                return chunk_summaries[0]

        except Exception as e:
            logger.error(f"Failed to summarize transcript: {e}", exc_info=True)
            # If summarization fails, return truncated transcript
            logger.warning("Using truncated transcript instead of summary")
            return transcript[:self.summarize_threshold]

    async def process_youtube_url(self, youtube_url: str, category: Optional[str] = None) -> dict:
        """
        Process a YouTube URL and return structured data for note creation.

        Args:
            youtube_url: YouTube video URL
            category: Optional category for the note

        Returns:
            Dictionary with:
                - content: Processed transcript text
                - title: Video title
                - video_id: YouTube video ID
                - url: Original YouTube URL
                - category: Category (if provided)

        Raises:
            ValueError: If URL is invalid or video cannot be processed
            RuntimeError: If processing fails
        """
        try:
            # Extract video ID
            video_id = self.extract_video_id(youtube_url)
            logger.info(f"Processing YouTube video: {video_id}")

            # Get video metadata (title, etc.)
            video_info = self.get_video_info(video_id)
            logger.info(f"Video title: {video_info['title']}")

            # Try to get transcript from API first (existing captions)
            transcript = self.get_transcript_from_api(video_id)

            # If no transcript available, use Whisper API to transcribe audio
            if not transcript:
                logger.info("No captions found, attempting Whisper transcription...")
                try:
                    # Let Whisper auto-detect language (or we could pass language if known)
                    transcript = self.get_transcript_with_whisper(youtube_url, language=None)
                except RuntimeError as whisper_error:
                    # Check if it's a bot detection error
                    if "bot detection" in str(whisper_error).lower():
                        raise RuntimeError(
                            f"Cannot transcribe video '{video_info['title']}': "
                            "YouTube blocked download (bot detection) and no captions are available. "
                            "Please try a video with captions/subtitles enabled."
                        )
                    else:
                        raise whisper_error

            # Summarize if transcript is too long
            if len(transcript) > self.summarize_threshold:
                logger.info(f"Transcript exceeds threshold ({len(transcript)} > {self.summarize_threshold}), summarizing...")
                processed_text = self.summarize_transcript(transcript)
            else:
                processed_text = transcript

            logger.info("YouTube processing completed successfully")

            # Return structured data instead of just text
            # Note: Store normalized URL format for consistent duplicate detection
            normalized_url = f"https://www.youtube.com/watch?v={video_info['video_id']}"
            result = {
                "content": processed_text,
                "title": video_info["title"],
                "video_id": video_info["video_id"],
                "url": normalized_url,
            }

            # Add category if provided
            if category:
                result["category"] = category

            return result

        except ValueError as e:
            # Invalid URL
            raise e
        except Exception as e:
            logger.error(f"Failed to process YouTube video: {e}", exc_info=True)
            raise RuntimeError(f"Failed to process YouTube video: {e}")
