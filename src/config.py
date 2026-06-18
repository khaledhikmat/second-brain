"""Configuration module for the Notes System Processor."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).parent.parent
VAULT_PATH = Path(os.getenv("VAULT_PATH", BASE_DIR / "vault"))
QUEUE_PATH = BASE_DIR / "queue"
LOGS_PATH = BASE_DIR / "logs"

# Telegram configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID")

# Claude API configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Application configuration
BATCH_MODE = os.getenv("BATCH_MODE", "false").lower() == "true"
BATCH_INTERVAL_MINUTES = int(os.getenv("BATCH_INTERVAL_MINUTES", "60"))
BATCH_PROCESS_LIMIT = int(os.getenv("BATCH_PROCESS_LIMIT", "100"))
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8080"))
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0")

# Note categories
PREDEFINED_CATEGORIES = os.getenv(
    "PREDEFINED_CATEGORIES",
    "Sayings,Poetry,Jots,Islam,History,Strategy,Concepts,Path"
).split(",")

# Language folders
LANGUAGE_FOLDERS = {
    "ar": "arabic",
    "en": "english"
}

# Git Auto-Sync configuration
GIT_AUTO_COMMIT = os.getenv("GIT_AUTO_COMMIT", "false").lower() == "true"
GIT_AUTO_PUSH = os.getenv("GIT_AUTO_PUSH", "false").lower() == "true"
GIT_REMOTE_NAME = os.getenv("GIT_REMOTE_NAME", "origin")
GIT_BRANCH_NAME = os.getenv("GIT_BRANCH_NAME", "main")
GIT_COMMIT_MESSAGE_TEMPLATE = os.getenv("GIT_COMMIT_MESSAGE_TEMPLATE", "Add note: {title}")

# HTTP API configuration
HTTP_API_ENABLED = os.getenv("HTTP_API_ENABLED", "false").lower() == "true"
HTTP_API_KEY = os.getenv("HTTP_API_KEY")

# Dashboard configuration
DASHBOARD_ENABLED = os.getenv("DASHBOARD_ENABLED", "true").lower() == "true"
DASHBOARD_USERNAME = os.getenv("DASHBOARD_USERNAME", "admin")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD")

# YouTube Transcription configuration
YOUTUBE_ENABLED = os.getenv("YOUTUBE_ENABLED", "false").lower() == "true"
YOUTUBE_TRANSCRIPT_LANGUAGES = os.getenv("YOUTUBE_TRANSCRIPT_LANGUAGES", "en,ar").split(",")
YOUTUBE_SUMMARIZE_THRESHOLD = int(os.getenv("YOUTUBE_SUMMARIZE_THRESHOLD", "10000"))
YOUTUBE_CHUNK_SIZE = int(os.getenv("YOUTUBE_CHUNK_SIZE", "4000"))

# OpenAI API for YouTube transcription (Whisper)
# Required if YOUTUBE_ENABLED=true
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Database configuration
DATABASE_ENABLED = os.getenv("DATABASE_ENABLED", "true").lower() == "true"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR / 'notes.db'}")
DATABASE_ECHO = os.getenv("DATABASE_ECHO", "false").lower() == "true"
DATABASE_MAX_RETRY_COUNT = int(os.getenv("DATABASE_MAX_RETRY_COUNT", "3"))

# Validation
def validate_config():
    """Validate that required configuration is present."""
    errors = []

    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN is not set")

    if not TELEGRAM_ALLOWED_USER_ID:
        errors.append("TELEGRAM_ALLOWED_USER_ID is not set")

    if not ANTHROPIC_API_KEY:
        errors.append("ANTHROPIC_API_KEY is not set")

    # HTTP API validation
    if HTTP_API_ENABLED and not HTTP_API_KEY:
        errors.append("HTTP_API_ENABLED is true but HTTP_API_KEY is not set")

    # Dashboard validation
    if DASHBOARD_ENABLED and not DASHBOARD_PASSWORD:
        errors.append("DASHBOARD_ENABLED is true but DASHBOARD_PASSWORD is not set")

    # YouTube transcription validation
    if YOUTUBE_ENABLED and not OPENAI_API_KEY:
        errors.append("YOUTUBE_ENABLED is true but OPENAI_API_KEY is not set")

    if errors:
        raise ValueError(f"Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))

    # Create directories if they don't exist
    VAULT_PATH.mkdir(parents=True, exist_ok=True)
    LOGS_PATH.mkdir(parents=True, exist_ok=True)

    # Create language folders
    for lang_folder in LANGUAGE_FOLDERS.values():
        lang_path = VAULT_PATH / lang_folder
        lang_path.mkdir(exist_ok=True)

        # Create category subfolders
        for category in PREDEFINED_CATEGORIES:
            category_path = lang_path / category.lower()
            category_path.mkdir(exist_ok=True)

if __name__ == "__main__":
    validate_config()
    print("Configuration is valid!")
