from typing import Protocol


class IExporterService(Protocol):
    """Protocol defining the exporter interface."""

    def is_configured(self) -> bool:
        """Return True if the exporter is ready to upload."""
        ...

    def upload(self, filename: str, content: bytes) -> None:
        """
        Upload content as a file, replacing any existing file with the same name.

        Args:
            filename: Target filename (e.g. 'Arabic-Strategy.md')
            content:  UTF-8 encoded file content
        """
        ...
