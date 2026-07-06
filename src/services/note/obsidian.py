from typing import Any, Dict, Optional
from pathlib import Path

from src.services.setting.typex import ISettingService
from src.services.logger.typex import ILoggerService
from src.services.typex import SummarizerResult

# Obsidian Note Service
class ObsidianNoteService:
    def __init__(self, setting: ISettingService, logger: ILoggerService):
        self._setting = setting
        self._logger = logger

    async def generate_note(
            self,
            processed_data: SummarizerResult,
            message_id: Optional[int] = None
        ) -> Path:
        """
        Generate an Obsidian note from processed data.

        Args:
            processed_data: SummarizerResult containing structured note data
            message_id: Optional database message ID for storing metadata

        Returns:
            Path to the created note file
        """
        return NotImplementedError("Obsidian note generation is not implemented yet.")

