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
    def __init__(self, setting: ISettingService, logger: ILoggerService, text_summarizer_service: ISummarizerService, storage_service=None):
        self._setting = setting
        self._logger = logger
        self._text_summarizer_service = text_summarizer_service
        self._storage_service = storage_service

    async def summarize(
            self,
            channel: str,
            category: str,
            language: str,
            message: str,
            metadata: Optional[Dict[str, Any]] = None
        ) -> Optional [SummarizerResult]:        
        """
        Process an incoming message and create a summary.

        Args:
            channel: The channel to which the summary belongs
            category: The category of the note
            language: The language of the message
            message: The message content
            metadata: Optional dictionary containing additional metadata for the note
        """
        # pdf only works with Gemini models
        if self._setting.get_summarization_llm_provider() != "gemini":
            self._logger.error(f"Only Gemini models are supported.")
            return create_fallback_structure(message, language, channel, category)

        r2_temp_path = None
        try:
            pdf_path = message.strip()

            # Download from R2 if the path is an R2 object key
            if pdf_path.startswith("r2://"):
                r2_key = pdf_path[len("r2://"):]
                self._logger.info(f"Downloading from R2: {r2_key}")
                content = self._storage_service.download(r2_key)
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf', prefix='r2_') as tmp:
                    tmp.write(content)
                    r2_temp_path = tmp.name
                pdf_path = r2_temp_path

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
            client = genai.Client()
            uploaded_file = client.files.upload(file=temp_path)
            self._logger.info(f"Upload complete. Remote File Name: {uploaded_file.name}")

            metadata = {
                "source": "pdf",
                "reference": message.strip()
            }

            prompt = produce_summarization_prompt(language, "pdf")
            self._logger.debug(f"PDF prompt: {prompt}")

            response = client.models.generate_content(
                model=self._setting.get_summarization_model(),
                contents=[uploaded_file, prompt]
            )

            # produce consistent titles across all sources
            title_summary = await self._text_summarizer_service.summarize(channel, category, language, response.text)

            return process_response(response.text,
                title_summary.title,
                language,
                channel,     
                category,
                metadata)

        except Exception as e:
            raise ValueError(f"Error processing PDF file with Gemini: {e}")
        finally:
            # Cleanup remote storage.
            # Deleting the file from the API server after processing frees up your project storage quota.
            if uploaded_file and client:
                client.files.delete(name=uploaded_file.name)

            # Cleanup temporary local file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

            # Cleanup R2 download temp file
            if r2_temp_path and os.path.exists(r2_temp_path):
                os.unlink(r2_temp_path)

