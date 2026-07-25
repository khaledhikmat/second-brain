from typing import Any, Dict, Optional, List
import yaml
from pathlib import Path
from datetime import datetime
import re

from services.setting.typex import ISettingService
from services.logger.typex import ILoggerService
from services.syncer.typex import ISyncerService
from services.summarizer.typex import SummarizerResult
from services.note.format_manager import IFormatManager, ObsidianFormatManager, OkfFormatManager

# Generator Note Service
class GeneratorNoteService:
    def __init__(self, setting: ISettingService, logger: ILoggerService, syncer: Optional [ISyncerService], formatters: Optional [List[IFormatManager]]):
        self._setting = setting
        self._logger = logger
        self._syncer = syncer
        self._formatters = formatters or [ObsidianFormatManager(self._setting, self._logger)]

    async def generate_note(
            self,
            processed_data: SummarizerResult,
            message_id: Optional[int] = None
        ) -> Optional [List[Path]]:
        """
        Generate a note from processed data.

        Args:
            processed_data: SummarizerResult containing structured note data
            message_id: Optional database message ID for storing metadata

        Returns:
            Path to the created note file
        """
        self._logger.info(f"note: summary result {processed_data}")
        if not self._setting.get_vault_path():
            return None 

        note_paths = []
        for formatter in self._formatters:
            self._logger.info(f"note formatter: {formatter.get_name()}")
            note_path = await formatter.generate_n_format_note_content(processed_data)
            if not note_path:
                self._logger.error(f"failed to generate content for formatter {formatter.get_name()}")
            else:
                note_paths.append(note_path)

        if len(note_paths) == 0:
            self._logger.error("Unable to generate note content")
            return None

        # Git sync if enabled
        if self._syncer:
            for note_path in note_paths:
                
                try:
                    success = self._syncer.sync_note(note_path, processed_data.title)
                    if success:
                        self._logger.info(f"Successfully synced note to Git: {processed_data.title}")
                    else:
                        self._logger.warning(f"Git sync failed for note: {processed_data.title}")
                except Exception as e:
                    self._logger.error(f"Error during Git sync: {e}", exc_info=True)
                
                continue

        self._logger.info("Created note")
        return note_paths
