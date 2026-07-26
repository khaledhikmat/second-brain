"""
Telegram handler implementation with webhook support.
"""
from datetime import datetime, date, time, timedelta
from typing import Optional
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import pytz

from services.setting.typex import ISettingService
from services.logger.typex import ILoggerService
from services.data.typex import IDataService

class TelegramHandler:
    """
    Telegram handler implementation.
    Implements the ITelegramHandler protocol.
    """

    def __init__(
        self,
        setting_service: ISettingService,
        logger_service: ILoggerService,
        db_service: IDataService
    ):
        """
        Initialize the Telegram handler.

        Args:
            setting_service: Setting service instance
            logger_service: Logger service instance
            db_service: Database service instance
            message_handler: Message handler instance
        """
        self._setting = setting_service
        self._logger = logger_service        
        self._db_service = db_service
        self.bot_token = self._setting.get_telegram_bot_token()
        self.application: Optional[Application] = None

    async def initialize(self) -> None:
        """Initialize the Telegram bot application."""
        try:
            # Build the application
            self.application = Application.builder().token(self.bot_token).build()

            # Register command handlers
            self.application.add_handler(CommandHandler("jot", self._handle_jot))
            self.application.add_handler(CommandHandler("islam", self._handle_islam))
            self.application.add_handler(CommandHandler("strategy", self._handle_strategy))
            self.application.add_handler(CommandHandler("history", self._handle_history))
            self.application.add_handler(CommandHandler("concept", self._handle_concept))
            self.application.add_handler(CommandHandler("future", self._handle_future))
            self.application.add_handler(CommandHandler("saying", self._handle_saying))
            self.application.add_handler(CommandHandler("poetry", self._handle_poetry))

            self.application.add_handler(CommandHandler("report", self._handle_report))
            self.application.add_handler(CommandHandler("help", self._handle_help))

            # Initialize the application
            await self.application.initialize()
            self._logger.info("Telegram bot initialized successfully")

        except Exception as e:
            self._logger.error(f"Failed to initialize Telegram bot: {e}")
            raise

    async def handle_webhook(self, update_data: dict) -> None:
        """
        Handle incoming webhook updates from Telegram.

        Args:
            update_data: The webhook update data from Telegram
        """
        try:
            if not self.application:
                self._logger.error("Telegram application not initialized")
                return

            # Convert the update data to an Update object
            update = Update.de_json(update_data, self.application.bot)

            # Process the update
            await self.application.process_update(update)

        except Exception as e:
            self._logger.error(f"Error handling webhook update: {e}")

    async def set_webhook(self, webhook_url: str) -> bool:
        """
        Set the webhook URL for the Telegram bot.

        Args:
            webhook_url: The URL where Telegram should send updates

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.application:
                self._logger.error("Telegram application not initialized")
                return False

            # Validate webhook URL is not empty
            if not webhook_url or not webhook_url.strip():
                self._logger.error("Webhook URL is empty or not set. Check TELEGRAM_WEBHOOK_URL environment variable.")
                return False

            # Validate it's a proper HTTPS URL
            if not webhook_url.startswith("https://"):
                self._logger.error(f"Webhook URL must start with https://. Got: {webhook_url}")
                return False

            await self.application.bot.set_webhook(url=webhook_url)
            self._logger.info(f"Webhook set to: {webhook_url}")
            return True
        except Exception as e:
            self._logger.error(f"Failed to set webhook: {e}")
            return False

    async def delete_webhook(self) -> bool:
        """
        Delete the webhook for the Telegram bot.

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.application:
                self._logger.error("Telegram application not initialized")
                return False
            await self.application.bot.delete_webhook()
            self._logger.info("Webhook deleted")
            return True
        except Exception as e:
            self._logger.error(f"Failed to delete webhook: {e}")
            return False

    # ========================================================================
    # Command Handlers
    # ========================================================================

    async def _handle_jot(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        return await self._handle_common_category(update, context, "jot")

    async def _handle_islam(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        return await self._handle_common_category(update, context, "islam")

    async def _handle_strategy(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        return await self._handle_common_category(update, context, "strategy")

    async def _handle_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        return await self._handle_common_category(update, context, "history")

    async def _handle_concept(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        return await self._handle_common_category(update, context, "concept")

    async def _handle_future(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        return await self._handle_common_category(update, context, "future")

    async def _handle_saying(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        return await self._handle_common_category(update, context, "saying")

    async def _handle_poetry(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        return await self._handle_common_category(update, context, "poetry")

    async def _handle_common_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE, category: str) -> None:
        try:
        # Parse the command arguments
            if not context.args or len(context.args) < 1:
                await update.message.reply_text(
                    "❌ Invalid command format.\n"
                    f"Usage: /{category} <message>\n"
                    f"Example: /{category} <message>"
                )
                return

            message = " ".join(context.args[1:])

            # Enqueue the message
            created_message = await self._db_service.create_message(
                raw_text=message,
                category=category,
                channel="telegram"
            )

            await update.message.reply_text(
                f"✅ {category} message has been queued.\n"
                f"Message ID: {created_message.id}"
            )

        except Exception as e:
            self._logger.error(f"Error handling /{category} command: {e}")
            await update.message.reply_text(
                f"❌ An error occurred while processing your message for category {category}. "
                "Please try again later."
            )

    async def _handle_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /report command.
        Format: /report
        """
        try:
            total_messages = await self.data_svc.get_total_messages()
            success_rate = await self.data_svc.get_success_rate()
            message_counts = await self.data_svc.get_message_counts_by_category()

            report_date = datetime.now().date()
            display_date = f"today ({report_date.strftime('%Y-%m-%d')})"

            # Calculate the total score
            report_lines = [
                f"📊 *Report for Second Brain*",
                f"📅 Date: {display_date}",
                f"",
            ]

            report_lines.extend([
                f"",
                f"*Summary:*",
                f"Total Messages: {total_messages}",
                f"Success Rate: {success_rate:.2f}%",
            ])

            for category, count in message_counts.items():
                report_lines.append(f"{category.capitalize()}: {count}")

            # Send the report
            report_text = "\n".join(report_lines)
            await update.message.reply_text(
                report_text,
                parse_mode="Markdown"
            )

        except Exception as e:
            self._logger.error(f"Error handling /report command: {e}")
            await update.message.reply_text(
                "❌ An error occurred while generating the report. "
                "Please try again later."
            )

    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /help command.
        Shows available commands.
        """
        help_text = """
🤖 *Second Brain Bot - Available Commands*

📝 */<category> <message>*
   Post a message for a specific category
   Supported Categories: jot, islam, strategy, history, concept, future, saying, poetry
   Example: `/jot This is a great idea!`

📊 */report*
   Get counts of messages and final score for a recipient on a specific date.

❓ */help*
   Show this list of commands

---
For support, contact your team administrator.
        """

        await update.message.reply_text(help_text, parse_mode="Markdown")
        self._logger.info(f"Help command executed by user {update.effective_user.id}")
