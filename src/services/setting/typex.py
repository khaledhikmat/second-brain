from typing import Protocol

from anyio import Path

class ISettingService(Protocol):
    """Protocol defining the setting interface."""

    def get_logs_path(self) -> Path: 
        """
        Get the path to the logs directory.

        Returns:
            The path to the logs directory
        """
        ...

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
