from typing import Protocol
from telegram import Update


class ITelegramHandler(Protocol):
    """Protocol defining the Telegram handler interface."""

    async def initialize(self) -> None:
        """Initialize the Telegram bot."""
        ...

    async def handle_webhook(self, update_data: dict) -> None:
        """
        Handle incoming webhook updates from Telegram.

        Args:
            update_data: The webhook update data from Telegram
        """
        ...

    async def set_webhook(self, webhook_url: str) -> bool:
        """
        Set the webhook URL for the Telegram bot.

        Args:
            webhook_url: The URL where Telegram should send updates

        Returns:
            True if successful, False otherwise
        """
        ...

    async def delete_webhook(self) -> bool:
        """
        Delete the webhook for the Telegram bot.

        Returns:
            True if successful, False otherwise
        """
        ...
