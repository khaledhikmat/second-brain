"""
Batch processor for the Rewards System.
This module handles:
- Dequeuing messages from the database
- Processing messages using the message handler
- Updating message status

This script is designed to run as a cron job.
"""
import os
import logging
import asyncio
from datetime import datetime
from dotenv import load_dotenv

from src.services.setting.envars import EnvVarsSettingService
from src.services.logger.dual import DualLoggerService
from src.services.data.postgres import PostgresDataService
from src.services.data.typex import MessageStatus
from src.services.syncer.git import GitSyncerService
from src.services.summarizer.pdf_via_gemini import PdfSummarizerService
from src.services.summarizer.text_via_claude import TextSummarizerService
from src.services.summarizer.youtube import YoutubeSummarizerService
from src.services.summarizer.router import RouterSummarizerService
from src.services.transcriber.whisper import WhisperTranscriberService
from src.services.note.okf import OkfNoteService
from src.services.note.obsidian import ObsidianNoteService

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def process_batch():
    """
    Main batch processing function.
    Dequeues messages and processes them.
    """
    db_service = None

    try:
        # Generate unique worker ID for this processor instance
        worker_id = MessageRepository._generate_worker_id()

        settings_service = EnvVarsSettingService()
        logger_service = DualLoggerService(settings_service)
        logger_service.info(f"Starting batch processor with worker ID: {worker_id}")
        logger_service.info(f"Batch size: {settings_service.get_batch_size()}")

        # Initialize database service
        logger_service.info("Connecting to database...")
        db_service = PostgresDataService(settings_service, logger_service)

        # Get queued evaluations
        logger_service.info("Fetching queued evaluations...")
        messages = await db_service.dequeue_messages(limit=settings_service.get_batch_size(), worker_id=worker_id)

        if not messages:
            logger_service.info("No queued messages found")
            return

        logger_service.info(f"Processing {len(messages)} messages...")

        # Transcriber Service
        transcriber_service = WhisperTranscriberService(settings_service, logger_service)

        # Summarizer Services
        text_summarizer_service = TextSummarizerService(settings_service, logger_service)
        pdf_summarizer_service = PdfSummarizerService(settings_service, logger_service)
        youtube_summarizer_service = YoutubeSummarizerService(settings_service, logger_service, transcriber_service, text_summarizer_service)
        router_summarizer_service = RouterSummarizerService(settings_service, logger_service, text_summarizer_service, youtube_summarizer_service, pdf_summarizer_service)

        # Git Syner
        syncer_service = GitSyncerService(settings_service, logger_service)

        # Note Service
        note_service = OkfNoteService(settings_service, logger_service, syncer_service)

        # Process each evaluation
        processed_count = 0
        failed_count = 0

        for message in messages:
            try:
                logger_service.info(f"Processing evaluation {message.id}...")

                # summarize message
                summary_results = await router_summarizer_service.summarize(message.id)
                if summary_results is None:
                    logger_service.error(f"Failed to summarize evaluation {message.id}")
                    raise ValueError(f"Failed to summarize evaluation {message.id}")

                # generate note
                file_path = note_service.generate_note(summary_results, message.id)
                logger_service.info(f"Note generated at {file_path} for message {message.id}")

                # update message status in database
                success = await db_service.update_message(message.id, MessageStatus.PROCESSED)
                if not success:
                    logger_service.error(f"Failed to update message status for {message.id}")

                processed_count += 1
                logger.info(f"Successfully processed message {message.id}")

            except Exception as e:
                failed_count += 1
                # update message status in database
                success = await db_service.update_message(message.id, MessageStatus.FAILED, str(e))
                if not success:
                    logger_service.error(f"Failed to update message status for {message.id}")
                logger.error(f"Error processing message {message.id}: {e}")

        # Log summary
        logger.info(
            f"Batch processing complete. "
            f"Processed: {processed_count}, Failed: {failed_count}, "
            f"Total: {len(messages)}"
        )

    except Exception as e:
        logger.error(f"Error in batch processing: {e}")
        raise

    finally:
        # Cleanup
        if db_service:
            logger.info("Disconnecting from database...")
            await db_service.finalize()

        logger.info("Batch processor finished")


def main():
    """Main entry point."""
    start_time = datetime.now()
    logger.info(f"Batch processor started at {start_time}")

    try:
        # Run the batch processing
        asyncio.run(process_batch())

    except Exception as e:
        logger.error(f"Fatal error in batch processor: {e}")
        raise

    finally:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"Batch processor completed in {duration:.2f} seconds")


if __name__ == "__main__":
    main()
