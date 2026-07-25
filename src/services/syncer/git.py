import subprocess
from pathlib import Path

from services.setting.typex import ISettingService
from services.logger.typex import ILoggerService

class GitSyncerService:
    """Sync vault using Git."""
    def __init__(self, setting: ISettingService, logger: ILoggerService):
        self._setting = setting
        self._logger = logger

        self.vault_path = self._setting.get_vault_path()
        self.vault_remote_url = self._setting.get_vault_repo_url()
        self.remote_name = self._setting.get_vault_remote_name()
        self.branch_name = self._setting.get_vault_branch_name()
        self.commit_message_template = self._setting.get_vault_commit_message_template()
        self._check_git_available()

    def sync_note(self, note_path: Path, note_title: str) -> bool:
        """
        Sync a note to Git (commit and optionally push).

        Args:
            note_path: Path to the note file
            note_title: Title of the note for commit message

        Returns:
            True if sync succeeded, False otherwise
        """
        try:
            if not self.vault_path or not self.vault_remote_url or not self.remote_name or not self.branch_name:
                return False

            # Get relative path for git add
            relative_path = note_path.relative_to(self.vault_path)

            # Stage the file
            self._logger.info(f"Staging file: {relative_path}")
            result = subprocess.run(
                ["git", "add", str(relative_path)],
                cwd=self.vault_path,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                self._logger.error(f"Git add failed: {result.stderr}")
                return False

            # Create commit message
            commit_message = self.commit_message_template.format(title=note_title)

            # Commit the change
            self._logger.info(f"Committing: {commit_message}")
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
                    self._logger.debug("Nothing to commit (file may already be committed)")
                    return True
                else:
                    self._logger.error(f"Git commit failed: {result.stderr}")
                    return False

            self._logger.info(f"Successfully committed note: {note_title}")

            # Push if enabled
            return self._push_changes()

        except Exception as e:
            self._logger.error(f"Git sync failed: {e}")
            return False

    def _check_git_available(self) -> bool:
        """Check if Git is available and vault is a Git repository."""
        try:
            if self.vault_path is None or not self.vault_path.exists():
                self._logger.warning("Vault path is not set or does not exist. Git sync will be disabled.")
                return False
            
            # Check if git command exists
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                self._logger.warning("Git is not available. Auto-commit will be disabled.")
                self.vault_path = None
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
                self._logger.warning(
                    f"Vault at {self.vault_path} is not a Git repository. "
                    "Auto-commit will be disabled. "
                    "Run 'git init' in the vault directory to enable Git sync."
                )
                self.vault_path = None
                return False

            self._logger.info("Git is available and vault is a Git repository")
            return True

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            self._logger.warning(f"Git check failed: {e}. Auto-commit will be disabled.")
            self.vault_path = None
            return False

    def _push_changes(self) -> bool:
        """
        Push committed changes to remote.

        Returns:
            True if push succeeded, False otherwise
        """
        try:
            self._logger.info(f"Pushing to {self.remote_name}/{self.branch_name}")
            result = subprocess.run(
                ["git", "push", self.remote_name, self.branch_name],
                cwd=self.vault_path,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                self._logger.error(f"Git push failed: {result.stderr}")
                return False

            self._logger.info("Successfully pushed changes to remote")
            return True

        except subprocess.TimeoutExpired:
            self._logger.error("Git push timed out after 30 seconds")
            return False
        except Exception as e:
            self._logger.error(f"Git push failed: {e}")
            return False


