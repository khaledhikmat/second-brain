"""Git synchronization utility for automatic commits and pushes."""

import logging
from pathlib import Path
from typing import Optional
import subprocess

logger = logging.getLogger(__name__)


class GitSync:
    """Handles Git operations for vault synchronization."""

    def __init__(
        self,
        vault_path: Path,
        auto_commit: bool = False,
        auto_push: bool = False,
        remote_name: str = "origin",
        branch_name: str = "main",
        commit_message_template: str = "Add note: {title}"
    ):
        """
        Initialize Git sync.

        Args:
            vault_path: Path to the vault directory
            auto_commit: Whether to auto-commit changes
            auto_push: Whether to auto-push to remote
            remote_name: Git remote name
            branch_name: Git branch name
            commit_message_template: Template for commit messages
        """
        self.vault_path = vault_path
        self.auto_commit = auto_commit
        self.auto_push = auto_push
        self.remote_name = remote_name
        self.branch_name = branch_name
        self.commit_message_template = commit_message_template

        if self.auto_commit:
            self._check_git_available()

    def _check_git_available(self) -> bool:
        """Check if Git is available and vault is a Git repository."""
        try:
            # Check if git command exists
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                logger.warning("Git is not available. Auto-commit will be disabled.")
                self.auto_commit = False
                self.auto_push = False
                return False

            # Check if vault is a git repository
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.vault_path,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                logger.warning(
                    f"Vault at {self.vault_path} is not a Git repository. "
                    "Auto-commit will be disabled. "
                    "Run 'git init' in the vault directory to enable Git sync."
                )
                self.auto_commit = False
                self.auto_push = False
                return False

            logger.info("Git is available and vault is a Git repository")
            return True

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"Git check failed: {e}. Auto-commit will be disabled.")
            self.auto_commit = False
            self.auto_push = False
            return False

    def sync_note(self, note_path: Path, note_title: str) -> bool:
        """
        Sync a note to Git (commit and optionally push).

        Args:
            note_path: Path to the note file
            note_title: Title of the note for commit message

        Returns:
            True if sync succeeded, False otherwise
        """
        if not self.auto_commit:
            logger.debug("Git auto-commit is disabled, skipping sync")
            return True

        try:
            # Get relative path for git add
            relative_path = note_path.relative_to(self.vault_path)

            # Stage the file
            logger.info(f"Staging file: {relative_path}")
            result = subprocess.run(
                ["git", "add", str(relative_path)],
                cwd=self.vault_path,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                logger.error(f"Git add failed: {result.stderr}")
                return False

            # Create commit message
            commit_message = self.commit_message_template.format(title=note_title)

            # Commit the change
            logger.info(f"Committing: {commit_message}")
            result = subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=self.vault_path,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                # Check if it's just "nothing to commit"
                if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
                    logger.debug("Nothing to commit (file may already be committed)")
                    return True
                else:
                    logger.error(f"Git commit failed: {result.stderr}")
                    return False

            logger.info(f"Successfully committed note: {note_title}")

            # Push if enabled
            if self.auto_push:
                return self._push_changes()

            return True

        except Exception as e:
            logger.error(f"Git sync failed: {e}", exc_info=True)
            return False

    def _push_changes(self) -> bool:
        """
        Push committed changes to remote.

        Returns:
            True if push succeeded, False otherwise
        """
        try:
            logger.info(f"Pushing to {self.remote_name}/{self.branch_name}")
            result = subprocess.run(
                ["git", "push", self.remote_name, self.branch_name],
                cwd=self.vault_path,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                logger.error(f"Git push failed: {result.stderr}")
                return False

            logger.info("Successfully pushed changes to remote")
            return True

        except subprocess.TimeoutExpired:
            logger.error("Git push timed out after 30 seconds")
            return False
        except Exception as e:
            logger.error(f"Git push failed: {e}", exc_info=True)
            return False

    def configure_git_user(self, name: str = "Notes System Bot", email: str = "bot@localhost") -> bool:
        """
        Configure Git user for commits (useful for new repositories).

        Args:
            name: Git user name
            email: Git user email

        Returns:
            True if configuration succeeded, False otherwise
        """
        try:
            # Set user name
            subprocess.run(
                ["git", "config", "user.name", name],
                cwd=self.vault_path,
                capture_output=True,
                timeout=5
            )

            # Set user email
            subprocess.run(
                ["git", "config", "user.email", email],
                cwd=self.vault_path,
                capture_output=True,
                timeout=5
            )

            logger.info(f"Configured Git user: {name} <{email}>")
            return True

        except Exception as e:
            logger.error(f"Failed to configure Git user: {e}")
            return False


def init_vault_git_repo(vault_path: Path) -> bool:
    """
    Initialize the vault as a Git repository if not already.

    Args:
        vault_path: Path to the vault directory

    Returns:
        True if initialization succeeded or repo already exists, False otherwise
    """
    try:
        # Check if already a git repo
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=vault_path,
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            logger.info("Vault is already a Git repository")
            return True

        # Initialize new repo
        logger.info(f"Initializing Git repository in {vault_path}")
        result = subprocess.run(
            ["git", "init"],
            cwd=vault_path,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            logger.error(f"Git init failed: {result.stderr}")
            return False

        # Create .gitignore
        gitignore_path = vault_path / ".gitignore"
        if not gitignore_path.exists():
            with open(gitignore_path, "w") as f:
                f.write("# Obsidian\n")
                f.write(".obsidian/\n")
                f.write(".trash/\n")

        logger.info("Successfully initialized Git repository")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize Git repository: {e}")
        return False
