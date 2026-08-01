from typing import Protocol

from pathlib import Path

class ISettingService(Protocol):
    """Protocol defining the setting interface."""

    ## logs
    def get_logs_path(self) -> Path: 
        """
        Get the path to the logs directory.

        Returns:
            The path to the logs directory
        """
        ...

    ## http
    def get_http_api_key(self) -> str:
        """
        Get the HTTP API key for authentication.

        Returns:
            The HTTP API key
        """
        ...

    def get_http_admin_username(self) -> str:
        """
        Get the HTTP admin username for authentication.

        Returns:
            The HTTP admin username
        """
        ...   

    def get_http_admin_password(self) -> str:
        """
        Get the HTTP admin password for authentication.

        Returns:
            The HTTP admin password
        """
        ...         

    def get_http_templates_dir(self) -> Path:
        """
        Get the path to the HTTP templates directory.

        Returns:
            The path to the HTTP templates directory
        """
        ...

    def get_note_templates_dir(self) -> Path:
        """
        Get the path to the note templates directory.

        Returns:
            The path to the note templates directory
        """
        ...

    def get_http_host(self) -> str:
        """
        Get the HTTP server host.

        Returns:
            The host to bind to (0.0.0.0 for production, localhost for dev)
        """
        ...

    def get_http_port(self) -> int:
        """
        Get the HTTP server port.

        Returns:
            The port number to bind to
        """
        ...

    ## telegram
    def get_telegram_bot_token(self) -> str:
        """
        Get the Telegram bot token.

        Returns:
            The Telegram bot token
        """
        ...

    def get_telegram_allowed_user_ids(self) -> list[str]:
        """
        Get the list of allowed Telegram user IDs.

        Returns:
            A list of allowed Telegram user IDs
        """
        ...

    ## database
    def get_database_url(self) -> str:
        """
        Get the database connection URL.

        Returns:
            The database connection URL
        """
        ...

    def get_database_echo(self) -> bool:
        """
        Get the database echo setting.

        Returns:
            True if SQL statements should be echoed, False otherwise
        """
        ...

    def get_database_max_retry_count(self) -> int:
        """
        Get the maximum number of retry attempts for database operations.

        Returns:
            The maximum number of retry attempts
        """
        ...

    ## summarization
    def get_summarization_llm_provider(slf) -> str:
        """
        Get the llm model to use for summarization.

        Returns:
            The llm model type for summarization
        """
        ...

    def get_summarization_model(self) -> str:
        """
        Get the model to use for summarization.

        Returns:
            The model name for summarization
        """
        ...

    def get_summarization_advanced_model(self) -> str:
        """
        Get the advanced model to use for summarization.

        Returns:
            The advanced model name for summarization
        """
        ...

    def get_summarization_threshold(self) -> int:
        """
        Get gemini threshold for summarization.

        Returns:
            The character length threshold for summarization
        """
        ...

    def get_summarization_chunk_size(self) -> int:
        """
        Get gemini chunk size for splitting long messages.

        Returns:
            The chunk size in characters
        """
        ...
    
    def get_summarization_api_key(self) -> str:
        """
        Get the API key for Gemini.

        Returns:
            The API key for Gemini
        """
        ...

    ## transcriber
    def get_transcriber_openai_api_key(self) -> str:
        """
        Get the OpenAI API key for transcription.

        Returns:
            The OpenAI API key
        """
        ...

    def get_transcriber_supadata_api_key(self) -> str:
        """
        Get the Supadata API key for YouTube transcript fetching.

        Returns:
            The Supadata API key
        """
        ...

    ## vault
    def get_vault_path(self) -> Path:
        """
        Get the path to the vault directory.

        Returns:
            The path to the vault directory
        """
        ...

    def get_vault_repo_url(self) -> str:
        """
        Get the URL of the vault repository.

        Returns:
            The URL of the vault repository
        """
        ...

    def get_vault_remote_name(self) -> str:
        """
        Get the name of the remote for Git sync.

        Returns:
            The remote name (e.g., 'origin')
        """
        ...

    def get_vault_branch_name(self) -> str:
        """
        Get the name of the branch for Git sync.

        Returns:
            The branch name (e.g., 'main')
        """
        ...

    def get_vault_commit_message_template(self) -> str:
        """
        Get the commit message template for Git sync.

        Returns:
            The commit message template (e.g., 'Update note: {title}')
        """
        ...

    ## batch processing
    def get_batch_size(self) -> int:
        """
        Get the batch size for processing messages.

        Returns:
            The number of messages to process per batch
        """
        ...
