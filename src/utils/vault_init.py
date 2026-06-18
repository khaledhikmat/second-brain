"""Vault initialization utility for cloud deployments."""

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


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
    # Get repo URL from parameter or environment
    repo_url = repo_url or os.getenv("VAULT_REPO_URL")

    # Check if vault already has .git directory
    git_dir = vault_path / ".git"
    if git_dir.exists():
        logger.info(f"Vault already initialized at {vault_path}")
        return True

    # If no repo URL, just create empty vault structure
    if not repo_url:
        logger.info("No VAULT_REPO_URL provided, creating empty vault structure")
        return _create_empty_vault(vault_path)

    # Clone repository
    logger.info(f"Initializing vault by cloning from remote repository...")
    try:
        # Ensure parent directory exists
        vault_path.parent.mkdir(parents=True, exist_ok=True)

        # Clone repository
        result = subprocess.run(
            ["git", "clone", repo_url, str(vault_path)],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            logger.error(f"Failed to clone vault repository: {result.stderr}")
            # Fall back to creating empty vault
            return _create_empty_vault(vault_path)

        logger.info("Successfully cloned vault repository")

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

    except subprocess.TimeoutExpired:
        logger.error("Git clone timed out after 60 seconds")
        return _create_empty_vault(vault_path)
    except Exception as e:
        logger.error(f"Error cloning vault repository: {e}", exc_info=True)
        return _create_empty_vault(vault_path)


def _create_empty_vault(vault_path: Path) -> bool:
    """
    Create empty vault structure with category folders.

    Args:
        vault_path: Path to the vault directory

    Returns:
        True if successful
    """
    try:
        logger.info(f"Creating empty vault structure at {vault_path}")

        # Categories
        categories = ["sayings", "poetry", "jots", "islam", "history", "strategy", "concepts", "path"]

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

        logger.info("Empty vault structure created successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to create empty vault: {e}", exc_info=True)
        return False


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
        logger.warning(f"Vault at {vault_path} is not a Git repository")
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
            logger.info(f"Git user already configured: {result.stdout.strip()}")
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

        logger.info("Git user configuration completed")
        return True

    except Exception as e:
        logger.error(f"Failed to configure Git user: {e}", exc_info=True)
        return False
