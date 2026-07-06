from typing import Protocol

class ILoggerService(Protocol):
    """Protocol defining the logger interface."""

    def debug(self, message: str) -> None:
        """
        Log an debug message.

        Args:
            message: The debug message to log
        """
        ...

    def info(self, message: str) -> None:
        """
        Log an info message.

        Args:
            message: The info message to log
        """
        ...

    def error(self, message: str, exp: Exception = None) -> None:
        """
        Log an error message.

        Args:
            message: The error message to log
            exp: The exception that caused the error
        """
        ...
