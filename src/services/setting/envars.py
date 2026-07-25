import os
from pathlib import Path

class EnvVarsSettingService:
    def __init__(self):
        # Initialize with environment variables or default values
        pass

    ## logs
    def get_logs_path(self) -> Path:
        # read from env variables or return a default path
        return Path(os.getenv("LOGS_PATH", "/logs"))
    
    # database
    def get_database_url(self) -> str:
        # read from env variables or return a default database URL
        return os.getenv("DATABASE_URL", "sqlite:///default.db")
    
    def get_database_echo(self) -> bool:
        # read from env variables or return a default value
        return os.getenv("DATABASE_ECHO", "False").lower() in ("true", "1", "t")

    ## http
    def get_http_api_key(self) -> str:
        """
        Get the HTTP API key for authentication.

        Returns:
            The HTTP API key
        """
        return os.getenv("HTTP_API_KEY", "change-this-api-key")

    def get_http_admin_username(self) -> str:
        """
        Get the HTTP admin username for authentication.

        Returns:
            The HTTP admin username
        """
        return os.getenv("HTTP_ADMIN_USERNAME", "admin")

    def get_http_admin_password(self) -> str:
        """
        Get the HTTP admin password for authentication.

        Returns:
            The HTTP admin password
        """
        return os.getenv("HTTP_ADMIN_PASSWORD", "admin")

    def get_http_templates_dir(self) -> Path:
        """
        Get the path to the HTTP templates directory.

        Returns:
            The path to the HTTP templates directory
        """
        return Path(os.getenv("HTTP_TEMPLATES_DIR", "src/templates"))

    def get_note_templates_dir(self) -> Path:
        """
        Get the path to the note templates directory.

        Returns:
            The path to the note templates directory
        """
        return Path(os.getenv("NOTE_TEMPLATES_DIR", "src/services/note/templates"))

    def get_http_host(self) -> str:
        # Production: 0.0.0.0 (bind to all interfaces)
        # Development: localhost (local only)
        return os.getenv("HTTP_HOST", "0.0.0.0")

    def get_http_port(self) -> int:
        # Default HTTP port
        return int(os.getenv("HTTP_PORT", "8080"))

    ## telegram
    def get_telegram_bot_token(self) -> str:
        """
        Get the Telegram bot token.

        Returns:
            The Telegram bot token
        """
        return os.getenv("TELEGRAM_BOT_TOKEN", "")

    def get_telegram_allowed_user_ids(self) -> list[str]:
        """
        Get the list of allowed Telegram user IDs.

        Returns:
            A list of allowed Telegram user IDs
        """
        return os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").split(",")
    
    ## summarization
    def get_summarization_llm_provider(slf) -> str:
        """
        Get the llm model to use for summarization.

        Returns:
            The llm model type for summarization
        """
        return os.getenv("SUMMARIZATION_LLM_PROVIDER", "gemini")

    def get_summarization_model(self) -> str:
        """
        Get the model to use for summarization.

        Returns:
            The model name for summarization
        """
        return os.getenv("SUMMARIZATION_MODEL", "gemini-3.5-flash")

    def get_summarization_advanced_model(self) -> str:
        """
        Get the model to use for summarization.

        Returns:
            The model name for summarization
        """
        return os.getenv("SUMMARIZATION_ADVANCED_MODEL", "gemini-3.5-pro")

    def get_summarization_threshold(self) -> int:
        """
        Get claude threshold for summarization.

        Returns:
            The character length threshold for summarization
        """
        return int(os.getenv("SUMMARIZATION_THRESHOLD", "1000000"))

    def get_summarization_chunk_size(self) -> int:
        """
        Get the chunk size for splitting long messages.

        Returns:
            The chunk size in characters
        """
        return int(os.getenv("SUMMARIZATION_CHUNK_SIZE", "4000"))

    
    def get_summarization_api_key(self) -> str:
        """
        Get the API key for Claude.

        Returns:
            The API key for Claude
        """
        return os.getenv("SUMMARIZATION_API_KEY", "")

    ## transcriber
    def get_transcriber_openai_api_key(self) -> str:
        """
        Get the OpenAI API key for transcription.

        Returns:
            The OpenAI API key
        """
        return os.getenv("TRANSCRIBER_OPENAI_API_KEY", "")

    ## vault
    def get_vault_path(self) -> Path:
        """
        Get the path to the vault directory.

        Returns:
            The path to the vault directory
        """
        return Path(os.getenv("VAULT_PATH", "./vault"))

    def get_vault_repo_url(self) -> str:
        """
        Get the URL of the vault repository.

        Returns:
            The URL of the vault repository
        """
        return os.getenv("VAULT_REPO_URL", "")

    def get_vault_remote_name(self) -> str:
        """
        Get the name of the remote for Git sync.

        Returns:
            The remote name (e.g., 'origin')
        """
        return os.getenv("GIT_REMOTE_NAME", "origin")

    def get_vault_branch_name(self) -> str:
        """
        Get the name of the branch for Git sync.

        Returns:
            The branch name (e.g., 'main')
        """
        return os.getenv("GIT_BRANCH_NAME", "main")

    def get_vault_commit_message_template(self) -> str:
        """
        Get the commit message template for Git sync.

        Returns:
            The commit message template (e.g., 'Update note: {title}')
        """
        return os.getenv("GIT_COMMIT_MESSAGE_TEMPLATE", "Add note: {title}")

    # batch
    def get_batch_size(self) -> int:
        """
        Get the batch size for processing messages.

        Returns:
            The number of messages to process per batch
        """
        return int(os.getenv("BATCH_PROCESS_LIMIT", "100"))
