"""
Batch entry point is designed to run as a cron job.
"""
import os
import socket
import uuid
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from typing import Optional, List

from services.setting.envars import EnvVarsSettingService
from services.logger.dual import DualLoggerService
from services.data.postgres import PostgresDataService
from services.data.typex import MessageStatus
from services.syncer.git import GitSyncerService
from services.summarizer.pdf import PdfSummarizerService
from services.summarizer.text import GeminiTextSummarizerService
from services.summarizer.youtube import YoutubeSummarizerService
from services.summarizer.router import RouterSummarizerService
from services.transcriber.whisper import WhisperTranscriberService
from services.note.generator import GeneratorNoteService
from services.note.format_manager import IFormatManager, ObsidianFormatManager, OkfFormatManager

# Load environment variables
load_dotenv()

async def process_batch():
    """
    Main batch processing function.
    Dequeues messages and processes them.
    """
    db_service = None

    settings_service = EnvVarsSettingService()
    logger_service = DualLoggerService(settings_service)

    try:
        # Initialize database service
        logger_service.info("Connecting to database...")
        db_service = PostgresDataService(settings_service, logger_service)
        await db_service.initialize()

        # Generate unique worker ID for this processor instance
        worker_id = _generate_worker_id()
        logger_service.info(f"Starting batch processor with worker ID: {worker_id}")
        logger_service.info(f"Batch size: {settings_service.get_batch_size()}")

        # Get queued messages from the database and lock them for processing by this worker
        logger_service.info("Fetching queued messages...")
        messages = await db_service.dequeue_messages(limit=settings_service.get_batch_size(), worker_id=worker_id)
        if not messages:
            logger_service.info("No queued messages found")
            return

        logger_service.info(f"Processing {len(messages)} messages...")

        # Transcriber Service
        transcriber_service = WhisperTranscriberService(settings_service, logger_service)

        # Summarizer Services
        text_summarizer_service = GeminiTextSummarizerService(settings_service, logger_service)
        pdf_summarizer_service = PdfSummarizerService(settings_service, logger_service)
        youtube_summarizer_service = YoutubeSummarizerService(settings_service, logger_service, transcriber_service, text_summarizer_service)
        router_summarizer_service = RouterSummarizerService(settings_service, logger_service, text_summarizer_service, youtube_summarizer_service, pdf_summarizer_service)

        # Git Syner
        syncer_service = GitSyncerService(settings_service, logger_service)

        # Note Service
        formatters: List[IFormatManager] = [ObsidianFormatManager(settings_service, logger_service)]
        note_service = GeneratorNoteService(settings_service, logger_service, syncer_service, formatters)

        # Process each evaluation
        processed_count = 0
        failed_count = 0

        for message in messages:
            try:
                logger_service.info(f"Processing evaluation {message.id}...")

                # summarize message
                summary_results = await router_summarizer_service.summarize(message.channel, message.raw_text, message.category, message.language)
                if summary_results is None:
                    logger_service.error(f"Failed to summarize message {message.id}")
                    raise ValueError(f"Failed to summarize message {message.id}")

                # generate note
                note_paths = await note_service.generate_note(summary_results, message.id)
                logger_service.info(f"note generated at {note_paths} for message {message.id}")
                if note_paths is None:
                    raise RuntimeError(f"Failed to generate note for {message.id}")

                for note_path in note_paths:
                    # create the note in the database
                    note = await db_service.create_note(message.id,
                        summary_results.title,
                        str(note_path),
                        summary_results.tags,
                        summary_results.concepts,
                        summary_results.entities,
                        summary_results.summary,
                        summary_results.model_dump()  # Convert Pydantic model to dict
                    )
                    if note is None:
                        raise RuntimeError(f"Failed to create note for {message.id}")
                
                # update message status in database
                success = await db_service.update_message(message.id, MessageStatus.COMPLETED, "", summary_results.language)
                if not success:
                    raise RuntimeError(f"Failed to update message status for {message.id}")

                processed_count += 1
                logger_service.info(f"Successfully processed message {message.id}")

            except Exception as e:
                failed_count += 1
                # update message status in database
                success = await db_service.update_message(message.id, MessageStatus.FAILED, str(e))
                if not success:
                    logger_service.error(f"Failed to update message status for {message.id}")
                logger_service.error(f"Error processing message {message.id}: {e}")

        # Log summary
        logger_service.info(
            f"Batch processing complete. "
            f"Processed: {processed_count}, Failed: {failed_count}, "
            f"Total: {len(messages)}"
        )

    except Exception as e:
        logger_service.error(f"Error in batch processing: {e}")
        raise

    finally:
        # Cleanup - shield from cancellation
        try:
            if db_service:
                logger_service.info("Disconnecting from database...")
                await asyncio.shield(db_service.finalize())
        except asyncio.CancelledError:
            logger_service.debug("Database cleanup cancelled")
        except Exception as e:
            logger_service.error(f"Error closing database: {e}")

        logger_service.info("Batch processor finished")

def _generate_worker_id() -> str:
    """
    Generate a unique worker identifier.

    Format: {hostname}-{pid}-{short-uuid}
    Example: myserver-1234-a3f2b

    Returns:
        Unique worker ID string
    """
    hostname = socket.gethostname()
    pid = os.getpid()
    short_uuid = str(uuid.uuid4())[:8]
    return f"{hostname}-{pid}-{short_uuid}"

def main():
    """Main entry point."""
    start_time = datetime.now()

    try:
        # Run the batch processing
        asyncio.run(process_batch())

    except Exception as e:
        print(f"Fatal error in batch processor: {e}")
        raise

    finally:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        print(f"Batch processor completed in {duration:.2f} seconds")


if __name__ == "__main__":
    main()
