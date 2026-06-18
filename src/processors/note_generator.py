"""Obsidian note generator with YAML frontmatter."""

import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import re

from src.db.database import get_db_manager
from src.db.repository import ProcessedNoteRepository

logger = logging.getLogger(__name__)


class ObsidianNoteGenerator:
    """Generates Obsidian-formatted notes with YAML frontmatter."""

    def __init__(
        self,
        vault_path: Path,
        language_folders: Dict[str, str],
        git_sync: Optional['GitSync'] = None
    ):
        """
        Initialize the note generator.

        Args:
            vault_path: Path to the Obsidian vault
            language_folders: Mapping of language codes to folder names
            git_sync: Optional GitSync instance for auto-commit
        """
        self.vault_path = vault_path
        self.language_folders = language_folders
        self.git_sync = git_sync

    def generate_note(self, processed_data: Dict[str, Any], message_id: Optional[int] = None) -> Path:
        """
        Generate an Obsidian note from processed data.

        Args:
            processed_data: Dictionary containing structured note data
            message_id: Optional database message ID for storing metadata

        Returns:
            Path to the created note file
        """
        language = processed_data.get("language", "en")
        category = processed_data.get("category", "Uncategorized")
        title = processed_data.get("title", "Untitled Note")

        # Create safe filename
        safe_filename = self._create_safe_filename(title)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{safe_filename}.md"

        # Determine the folder path
        lang_folder = self.language_folders.get(language, "english")
        category_folder = category.lower().replace(" ", "_")

        note_dir = self.vault_path / lang_folder / category_folder
        note_dir.mkdir(parents=True, exist_ok=True)

        note_path = note_dir / filename

        # Generate note content
        content = self._generate_note_content(processed_data)

        # Write the note
        with open(note_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"Created note: {note_path}")

        # Store note metadata in database if message_id provided
        if message_id:
            self._store_note_metadata(message_id, processed_data, note_path)

        # Git sync if enabled
        if self.git_sync:
            try:
                success = self.git_sync.sync_note(note_path, title)
                if success:
                    logger.info(f"Successfully synced note to Git: {title}")
                else:
                    logger.warning(f"Git sync failed for note: {title}")
            except Exception as e:
                logger.error(f"Error during Git sync: {e}", exc_info=True)
                # Continue anyway - note is created even if sync fails

        return note_path

    def _store_note_metadata(
        self,
        message_id: int,
        processed_data: Dict[str, Any],
        note_path: Path
    ):
        """
        Store note metadata in database.

        Args:
            message_id: Database message ID
            processed_data: Processed note data
            note_path: Path to the created note file
        """
        db_manager = get_db_manager()
        if not db_manager or not db_manager.is_available:
            logger.warning("Database unavailable, skipping note metadata storage")
            return

        try:
            import asyncio

            async def store():
                async with db_manager.get_session_safe() as session:
                    if session:
                        await ProcessedNoteRepository.create(
                            session,
                            message_id=message_id,
                            title=processed_data.get("title", "Untitled"),
                            file_path=str(note_path),
                            tags=processed_data.get("tags"),
                            concepts=processed_data.get("concepts"),
                            entities=processed_data.get("entities"),
                            summary=processed_data.get("summary"),
                            processed_data=processed_data
                        )
                        logger.info(f"Stored note metadata in database for message {message_id}")

            # Run async function in the current event loop if exists, or create new one
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Create a task if loop is running
                    asyncio.create_task(store())
                else:
                    # Run directly if loop is not running
                    loop.run_until_complete(store())
            except RuntimeError:
                # No event loop, create one
                asyncio.run(store())

        except Exception as e:
            logger.error(f"Failed to store note metadata: {e}", exc_info=True)

    def _create_safe_filename(self, title: str) -> str:
        """Create a safe filename from a title."""
        # Remove invalid characters
        safe = re.sub(r'[<>:"/\\|?*]', '', title)
        # Replace spaces with underscores
        safe = safe.replace(" ", "_")
        # Limit length
        safe = safe[:100]
        # Remove trailing periods and spaces
        safe = safe.rstrip(". ")
        return safe or "untitled"

    def _generate_note_content(self, data: Dict[str, Any]) -> str:
        """
        Generate the full note content with frontmatter.

        Args:
            data: Processed note data

        Returns:
            Complete note content as string
        """
        # Prepare simplified frontmatter
        frontmatter = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S"),
            "title": data.get("title", "Untitled"),
            "language": data.get("language", "en"),
            "category": data.get("category", "Uncategorized"),
            "source": data.get("source", "telegram"),  # telegram or http
            "created": datetime.now().isoformat(),
            "processed_at": data.get("processed_at")
        }

        # Add YouTube URL to frontmatter if present
        if data.get("url"):
            frontmatter["youtube_url"] = data.get("url")

        # Add fallback flag if present
        if data.get("fallback"):
            frontmatter["fallback"] = True

        # Generate YAML frontmatter
        yaml_str = yaml.dump(
            frontmatter,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False
        )

        # Build the complete note
        parts = [
            "---",
            yaml_str.strip(),
            "---",
            ""
        ]

        # Get category for conditional formatting
        category = data.get("category", "")

        # Simplified format for Poetry and Sayings categories
        if category.lower() in ["poetry", "sayings"]:
            # No title heading for Poetry and Sayings

            # Only include people (if any) and original text
            entities = data.get("entities", {})
            if entities.get("people"):
                parts.extend([
                    "## People",
                    "",
                    self._format_list_with_wikilinks(entities.get("people")),
                    ""
                ])

            # Add original text
            original_text = data.get("original_text")
            if original_text:
                parts.extend([
                    "---",
                    "",
                    "## Original Text",
                    "",
                    original_text,
                    ""
                ])
        else:
            # Full format for other categories
            # Add title heading
            parts.extend([
                f"# {data.get('title', 'Untitled')}",
                ""
            ])

            # Add summary if available
            if data.get("summary"):
                parts.extend([
                    "## Summary",
                    "",
                    data.get("summary"),
                    ""
                ])

            # Add main content
            parts.extend([
                "## Content",
                "",
                data.get("content", ""),
                ""
            ])

            # Add concepts section
            if data.get("concepts"):
                parts.extend([
                    "## Key Concepts",
                    "",
                    self._format_list(data.get("concepts")),
                    ""
                ])

            # Add entities sections
            entities = data.get("entities", {})
            if any(entities.values()):
                parts.append("## Entities")
                parts.append("")

                if entities.get("people"):
                    parts.append("### People")
                    parts.append("")
                    parts.append(self._format_list_with_wikilinks(entities.get("people")))
                    parts.append("")

                if entities.get("places"):
                    parts.append("### Places")
                    parts.append("")
                    parts.append(self._format_list_with_wikilinks(entities.get("places")))
                    parts.append("")

                if entities.get("terms"):
                    parts.append("### Terms")
                    parts.append("")
                    parts.append(self._format_list_with_wikilinks(entities.get("terms")))
                    parts.append("")

            # Add translations section (for Arabic notes)
            translations = data.get("translations", {})
            if translations:
                parts.append("## Translations")
                parts.append("")
                parts.append("| Arabic | English |")
                parts.append("|--------|---------|")
                for arabic, english in translations.items():
                    parts.append(f"| {arabic} | {english} |")
                parts.append("")

            # Add key terms section
            key_terms = data.get("key_terms", [])
            if key_terms and isinstance(key_terms, list):
                parts.append("## Key Terms")
                parts.append("")
                parts.append("| Term | Translation | Explanation |")
                parts.append("|------|-------------|-------------|")
                for term_obj in key_terms:
                    if isinstance(term_obj, dict):
                        term = term_obj.get("term", "").replace("|", "\\|")
                        translation = term_obj.get("translation", "").replace("|", "\\|")
                        explanation = term_obj.get("explanation", "").replace("|", "\\|")
                        parts.append(f"| {term} | {translation} | {explanation} |")
                parts.append("")

            # Add comparison table section
            comparison_table = data.get("comparison_table", {})
            if isinstance(comparison_table, dict) and comparison_table.get("present"):
                caption = comparison_table.get("caption", "Comparison Table")
                headers = comparison_table.get("headers", [])
                rows = comparison_table.get("rows", [])

                if headers and rows:
                    parts.append("## Comparison Table")
                    parts.append("")
                    parts.append(f"**{caption}**")
                    parts.append("")

                    # Format table headers
                    header_row = "| " + " | ".join(str(h).replace("|", "\\|") for h in headers) + " |"
                    separator = "|" + "|".join(["---" for _ in headers]) + "|"

                    parts.append(header_row)
                    parts.append(separator)

                    # Format table rows
                    for row in rows:
                        if isinstance(row, list):
                            row_str = "| " + " | ".join(str(cell).replace("|", "\\|") for cell in row) + " |"
                            parts.append(row_str)

                    parts.append("")

            # Add original text section
            original_text = data.get("original_text")
            if original_text:
                parts.extend([
                    "---",
                    "",
                    "## Original Text",
                    "",
                    original_text,
                    ""
                ])

        # Add metadata footer
        parts.extend([
            "---",
            ""
        ])

        # Add source information
        source = data.get("source", "telegram")
        # Normalize "http_api" to "http"
        if source == "http_api":
            source = "http"

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Add footer with source and timestamp
        parts.append(f"*Generated from {source} on {timestamp}*")

        # Add YouTube URL reference if present (without "Source:" label)
        if data.get("url"):
            parts.append("")
            parts.append(data.get("url"))

        return "\n".join(parts)

    def _format_list(self, items: list) -> str:
        """Format a list as markdown bullet points."""
        if not items:
            return ""
        return "\n".join(f"- {item}" for item in items)

    def _format_list_with_wikilinks(self, items: list) -> str:
        """Format a list with wikilinks."""
        if not items:
            return ""
        return "\n".join(f"- [[{item}]]" for item in items)
