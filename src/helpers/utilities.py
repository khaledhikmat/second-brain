import os
import re
from typing import Optional, List
import shutil
from langdetect import detect, LangDetectException
from pathlib import Path
import subprocess

def is_arabic(text: str) -> bool:
    """Check if text is primarily in Arabic."""
    return _detect_language(text) == "ar"


def is_english(text: str) -> bool:
    """Check if text is primarily in English."""
    return _detect_language(text) == "en"

def is_pdf_message(text: str) -> bool:
    """
    Check if text contains a PDF URL.

    Args:
        text: Text to check
    """
    return False

def is_youtube_url_message(text: str) -> bool:
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

def is_text_message(text: str) -> bool:
    """
    Check if the message is a text message (not a URL or file).

    Args:
        text: Text to check

    Returns:
        True if the message is a text message
    """
    return not (is_youtube_url_message(text) or is_pdf_message(text))

def init_vault_from_remote(vault_path: Path, repo_url: str = None) -> bool:
    """
    Initialize vault by cloning from remote repository if it doesn't exist.

    This is useful for cloud deployments where the vault needs to be
    initialized on first startup.

    Args:
        vault_path: Path to the vault directory
        repo_url: Git repository URL (with credentials if needed)
                 Can also be set via VAULT_REPO_URL environment variable

    Returns:
        True if vault is ready, False otherwise
    """
    # Check if vault already has .git directory
    git_dir = vault_path / ".git"
    if git_dir.exists():
        return True

    # If no repo URL, just create empty vault structure
    if not repo_url:
        return _create_empty_vault(vault_path)

    # Clone repository
    try:
        # Ensure parent directory exists
        vault_path.parent.mkdir(parents=True, exist_ok=True)

        # If vault directory exists but is not a git repo, remove it
        if vault_path.exists() and not git_dir.exists():
            shutil.rmtree(vault_path)

        # Clone repository
        result = subprocess.run(
            ["git", "clone", repo_url, str(vault_path)],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            # Fall back to creating empty vault
            return _create_empty_vault(vault_path)

        # Configure git user
        subprocess.run(
            ["git", "config", "user.name", "Notes System Bot"],
            cwd=vault_path,
            capture_output=True,
            timeout=5
        )
        subprocess.run(
            ["git", "config", "user.email", "bot@notes-system.local"],
            cwd=vault_path,
            capture_output=True,
            timeout=5
        )

        # Ensure all category folders exist
        _ensure_category_folders(vault_path)

        return True

    except subprocess.TimeoutExpired:
        return _create_empty_vault(vault_path)
    except Exception as e:
        return _create_empty_vault(vault_path)

def ensure_vault_git_configured(vault_path: Path) -> bool:
    """
    Ensure the vault has Git user configuration.

    Args:
        vault_path: Path to the vault directory

    Returns:
        True if configuration successful
    """
    git_dir = vault_path / ".git"
    if not git_dir.exists():
        return False

    try:
        # Check if user is already configured
        result = subprocess.run(
            ["git", "config", "user.name"],
            cwd=vault_path,
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0 and result.stdout.strip():
            return True

        # Configure git user
        subprocess.run(
            ["git", "config", "user.name", "Notes System Bot"],
            cwd=vault_path,
            capture_output=True,
            timeout=5
        )
        subprocess.run(
            ["git", "config", "user.email", "bot@notes-system.local"],
            cwd=vault_path,
            capture_output=True,
            timeout=5
        )

        return True

    except Exception as e:
        return False

## PRIVATE HELPERS
def _create_empty_vault(vault_path: Path) -> bool:
    """
    Create empty vault structure with category folders.

    Args:
        vault_path: Path to the vault directory

    Returns:
        True if successful
    """
    try:
        # Categories
        categories = ["sayings", "poetry", "jots", "islam", "history", "strategy", "concepts", "future"]

        # Create language folders and categories
        for lang in ["arabic", "english"]:
            for category in categories:
                category_path = vault_path / lang / category
                category_path.mkdir(parents=True, exist_ok=True)

        # Create .gitignore if it doesn't exist
        gitignore_path = vault_path / ".gitignore"
        if not gitignore_path.exists():
            with open(gitignore_path, "w") as f:
                f.write("# Obsidian\n")
                f.write(".obsidian/\n")
                f.write(".trash/\n")

        return True

    except Exception as e:
        return False


def _ensure_category_folders(vault_path: Path) -> bool:
    """
    Ensure all category folders exist in the vault.

    Args:
        vault_path: Path to the vault directory

    Returns:
        True if successful
    """
    try:
        # Categories from environment or defaults
        categories_str = os.getenv("PREDEFINED_CATEGORIES", "Sayings,Poetry,Jots,Islam,History,Strategy,Concepts,Path")
        categories = [cat.strip().lower() for cat in categories_str.split(",")]

        # Create language folders and categories
        for lang in ["arabic", "english"]:
            for category in categories:
                category_path = vault_path / lang / category
                if not category_path.exists():
                    category_path.mkdir(parents=True, exist_ok=True)

        return True

    except Exception as e:
        return False


def _detect_language(text: str) -> str:
    """
    Detect the language of the given text.

    Args:
        text: The text to analyze

    Returns:
        Language code ('ar' for Arabic, 'en' for English)
        Defaults to 'en' if detection fails
    """
    if not text or not text.strip():
        return "en"

    try:
        if len(text) > 5000:
            text = text[:5000]  # Limit to first 5000 characters for performance
        detected = detect(text)

        # Map to our supported languages
        if detected in ['ar', 'arabic']:
            return "ar"
        else:
            # Default to English for all other languages
            return "en"

    except LangDetectException as e:
        return "en"  # Default to English

