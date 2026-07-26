import subprocess
import shutil
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
        self._initialize_vault()

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
            if not self.vault_path:
                self._logger.error("Git sync failed: vault not initialized (vault_path is None)")
                return False
            if not self.vault_remote_url:
                self._logger.error("Git sync failed: VAULT_REPO_URL not configured")
                return False
            if not self.remote_name:
                self._logger.error("Git sync failed: GIT_REMOTE_NAME not configured")
                return False
            if not self.branch_name:
                self._logger.error("Git sync failed: GIT_BRANCH_NAME not configured")
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

    def _initialize_vault(self) -> bool:
        """Initialize vault by cloning repository if needed."""
        try:
            if not self.vault_path or not self.vault_remote_url:
                self._logger.warning("Vault path or remote URL not configured. Git sync disabled.")
                self.vault_path = None
                return False

            # Ensure vault path is a Path object
            if not isinstance(self.vault_path, Path):
                self.vault_path = Path(self.vault_path)

            # Check if git command exists
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                self._logger.warning("Git is not available. Git sync disabled.")
                self.vault_path = None
                return False

            # Check if vault directory exists
            if not self.vault_path.exists():
                self._logger.info(f"Creating vault directory: {self.vault_path}")
                self.vault_path.mkdir(parents=True, exist_ok=True)

            # Check if it's already a git repository
            is_git_repo = False
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.vault_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            is_git_repo = (result.returncode == 0)

            # If not a git repo or directory is empty, clone it
            if not is_git_repo or len(list(self.vault_path.iterdir())) == 0:
                self._logger.info(f"Cloning repository to {self.vault_path}")
                # Remove any existing content
                for item in self.vault_path.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)

                # Clone the repository
                result = subprocess.run(
                    ["git", "clone", self.vault_remote_url, "."],
                    cwd=self.vault_path,
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                if result.returncode != 0:
                    self._logger.error(f"Failed to clone repository: {result.stderr}")
                    self.vault_path = None
                    return False

                self._logger.info("Successfully cloned repository")
            else:
                # Already a git repo, verify remote and pull latest
                self._logger.info("Vault is already a git repository")

                # Ensure remote is configured correctly
                result = subprocess.run(
                    ["git", "remote", "get-url", self.remote_name],
                    cwd=self.vault_path,
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if result.returncode != 0:
                    # Remote doesn't exist, add it
                    self._logger.info(f"Adding remote '{self.remote_name}'")
                    subprocess.run(
                        ["git", "remote", "add", self.remote_name, self.vault_remote_url],
                        cwd=self.vault_path,
                        capture_output=True,
                        text=True,
                        timeout=5
                    )

                # Pull latest changes
                self._logger.info("Pulling latest changes")
                result = subprocess.run(
                    ["git", "pull", self.remote_name, self.branch_name],
                    cwd=self.vault_path,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode != 0:
                    self._logger.warning(f"Git pull failed (continuing anyway): {result.stderr}")

            self._logger.info("Git vault initialized successfully")
            return True

        except Exception as e:
            self._logger.error(f"Failed to initialize vault: {e}")
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


