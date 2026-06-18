"""Language detection module."""

from langdetect import detect, LangDetectException
import logging

logger = logging.getLogger(__name__)


def detect_language(text: str) -> str:
    """
    Detect the language of the given text.

    Args:
        text: The text to analyze

    Returns:
        Language code ('ar' for Arabic, 'en' for English)
        Defaults to 'en' if detection fails
    """
    if not text or not text.strip():
        logger.warning("Empty text provided for language detection")
        return "en"

    try:
        detected = detect(text)

        # Map to our supported languages
        if detected in ['ar', 'arabic']:
            return "ar"
        else:
            # Default to English for all other languages
            return "en"

    except LangDetectException as e:
        logger.error(f"Language detection failed: {e}")
        return "en"  # Default to English


def is_arabic(text: str) -> bool:
    """Check if text is primarily in Arabic."""
    return detect_language(text) == "ar"


def is_english(text: str) -> bool:
    """Check if text is primarily in English."""
    return detect_language(text) == "en"
