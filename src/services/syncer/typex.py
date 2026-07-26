from typing import Protocol
from pathlib import Path

class ISyncerService(Protocol):
    """Protocol defining the syncer interface."""

    def sync_note(self, note_path: Path, note_title: str) -> bool:
        """
        Sync a note with the vault.

        Args:
            note_path: The path to the note file
            note_title: The title of the note
        """
        ...
