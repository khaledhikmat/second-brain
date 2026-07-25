import os
from typing import Any, Dict, Optional
import tempfile
import shutil

from google import genai
from google.genai import types

from services.setting.typex import ISettingService
from services.logger.typex import ILoggerService
from services.summarizer.typex import ISummarizerService, SummarizerResult, produce_summarization_prompt, process_response, create_fallback_structure


class PdfSummarizerService:
    def __init__(self, setting: ISettingService, logger: ILoggerService):
        self._setting = setting
        self._logger = logger

    async def summarize(
            self,
            channel: str,
            message: str,
            category: str,
            language: str = None,
            title: Optional[str] = None,
            metadata: Optional[Dict[str, Any]] = None
        ) -> Optional [SummarizerResult]:        
        """
        Process an incoming message and create a note.

        Args:
            channel: The channel to which the summary belongs
            message: The incoming message
            category: The category of the note
            language: The language of the message
            specified_title: The title of the note (if specified)
            specified_category: The category of the note (if specified)
            metadata: Optional dictionary containing additional metadata for the note

        Returns:
            SummarizerResult: A structured result containing the summary and metadata.
        """
        try:
            # pdf only works with Gemini models
            if self._setting.get_summarization_llm_provider() != "gemini":
                self._logger.error(f"Gemini model is not available.")
                return create_fallback_structure(message, language, title, category)

            client = genai.Client()

            skip_summarization = False
            if category and category.lower() in ["sayings", "poetry"]:
                skip_summarization = True

            prompt = produce_summarization_prompt(category, language, message, skip_summarization)
            self._logger.debug(f"Prompt: {prompt}")

            pdf_path = message.strip()
            self._logger.info(f"Analyzing file: {pdf_path}")

            if not os.path.exists(pdf_path):
                raise FileNotFoundError(f"The file at {pdf_path} could not be found.")

            # Upload the file using the File API.
            # This natively handles massive files up to 2GB.
            # To handle Unicode filenames (e.g., Arabic), we create a temporary copy with ASCII-safe name
            original_name = os.path.basename(pdf_path)
            self._logger.info(f"Uploading '{original_name}' to Gemini File API...")

            # Create temporary file with ASCII-safe name
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf', prefix='gemini_upload_') as tmp_file:
                temp_path = tmp_file.name

            # Copy the original file to temp location
            shutil.copy2(pdf_path, temp_path)

            # Upload using the temp file (ASCII-safe path)
            uploaded_file = client.files.upload(file=temp_path)
            self._logger.info(f"Upload complete. Remote File Name: {uploaded_file.name}")

            try:
                response = client.models.generate_content(
                    model=self._setting.get_summarization_model(),
                    contents=[uploaded_file, prompt]
                )

                return process_response(message,
                    response.text,
                    channel,     
                    language,
                    category,
                    title,
                    {
                        "source": "pdf",
                        "reference": pdf_path
                    })

            except Exception as e:
                print(f"An error occurred during generation: {e}")

            finally:
                # Cleanup remote storage.
                # Deleting the file from the API server after processing frees up your project storage quota.
                client.files.delete(name=uploaded_file.name)

        except Exception as e:
            self._logger.error(f"Error processing message with Gemini: {e}")
            return create_fallback_structure(message, language, title, category)
        finally:
            # Cleanup temporary local file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

