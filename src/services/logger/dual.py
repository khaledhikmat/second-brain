import logging
from pathlib import Path

from src.services.setting.typex import ISettingService

class DualLoggerService:
    def __init__(self, setting: ISettingService):
        self._setting = setting
        # Setup logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self._setting.get_logs_path() / 'second_brain.log'),
                logging.StreamHandler()
            ]
        )
        self._logger = logging.getLogger(__name__)

    def debug(self, message: str):
        self._logger.debug(message)

    def info(self, message: str):
        self._logger.info(message)

    def error(self, message: str, exp: Exception = None):
        self._logger.error(message, exc_info=exp)