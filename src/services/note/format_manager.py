from typing import Optional, Protocol
import yaml
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape

from services.summarizer.typex import SummarizerResult
from services.setting.typex import ISettingService
from services.logger.typex import ILoggerService
from services.note.template_filters import CUSTOM_FILTERS

class IFormatManager(Protocol):
    """Protocol defining the note format manager interface."""

    def get_name(self) -> str:
        """
        Get note formatter name.

        Returns:
            Formatter name
        """
        ...

    async def generate_n_format_note_content(self, processed_data: SummarizerResult) -> Optional [Path]:        
        """
        Generate a note from processed data.

        Args:
            processed_data: SummarizerResult containing structured note data

        Returns:
            Note Path if successful
        """
        ...

class ObsidianFormatManager:
    def __init__(self, setting: ISettingService, logger: ILoggerService):
        self._setting = setting
        self._logger = logger

        # Initialize Jinja2 environment with custom filters
        templates_dir = self._setting.get_note_templates_dir()
        self._env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        # Register custom filters
        self._env.filters.update(CUSTOM_FILTERS)

    def get_name(self) -> str:
        """
        Get note formatter name.

        Returns:
            Formatter name
        """
        return "Obsidian"

    async def generate_n_format_note_content(self, processed_data: SummarizerResult) -> Optional [Path]:        
        """
        Generate an Obsidian-formmatted note from processed data.

        Args:
            processed_data: SummarizerResult containing structured note data

        Returns:
            Note path
        """
        self._logger.info(f"Obsidian note: summary result {processed_data}")
        if not self._setting.get_vault_path():
            return None 

        title = processed_data.title if processed_data.title else "untitled_note"

        # Create safe filename
        safe_filename = self._create_safe_filename(title)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{safe_filename}.md"

        # Determine the folder path
        formatter_folder = "obs"
        lang_folder = processed_data.language
        category_folder = processed_data.category.lower().replace(" ", "_")

        # Ensure vault_path is a Path object
        vault_path = Path(self._setting.get_vault_path())
        note_dir = vault_path / formatter_folder / lang_folder / category_folder
        note_dir.mkdir(parents=True, exist_ok=True)

        note_path = Path(note_dir / filename)

        # Generate note content
        content = self._generate_note_content(processed_data)

        # Write the note
        with open(note_path, "w", encoding="utf-8") as f:
            f.write(content)

        self._logger.info(f"Created note: {note_path}")

        return note_path

    def _generate_note_content(self, data: SummarizerResult) -> str:
        """
        Generate the full note content with frontmatter using Jinja2 template.

        Args:
            data: Processed note data

        Returns:
            Complete note content as string
        """
        category = data.category if data.category else "jot"
        channel = data.channel if data.channel else "telegram"

        # Prepare simplified frontmatter
        frontmatter = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S"),
            "category": category,
            "title": data.title if data.title else "untitled",
            "language": data.language if data.language else "en",
            "channel": channel,
            "created": datetime.now().isoformat(),
            "processed_at": data.processedAt if data.processedAt else datetime.now().isoformat(),
        }

        # Add Metadata URL to frontmatter if present
        if data.metadata:
            for key, val in data.metadata:
                frontmatter[key] = val

        # Generate YAML frontmatter string
        yaml_str = yaml.dump(
            frontmatter,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False
        )

        # Normalize context
        context = {
            "frontmatter": yaml_str.strip(),
            "category": category,
            "title": data.title if data.title else "untitled_note",
            "language": data.language if data.language else "ar",
            "channel": channel,
            "created": datetime.now().isoformat(),
            "summary": data.summary if data.summary else "",
            "content": data.content if data.content else "",
            "concepts": data.concepts if data.concepts else "",
            "entities": data.entities if data.entities else {},
            "original_text": data.content if data.content else "",
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

        # Include metadata
        if data.metadata:
            for k, v in data.metadata:
                context[k] = v

        # Render template
        template = self._env.get_template("obsidian.md.j2")
        return template.render(**context)

    def _create_safe_filename(self, title: str) -> str:
        """Create a safe filename from a title."""
        # Use the safe_filename filter
        return CUSTOM_FILTERS['safe_filename'](title)

class OkfFormatManager:
    def __init__(self, setting: ISettingService, logger: ILoggerService):
        self._setting = setting
        self._logger = logger

        # Initialize Jinja2 environment with custom filters
        templates_dir = self._setting.get_note_templates_dir()
        self._env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        # Register custom filters
        self._env.filters.update(CUSTOM_FILTERS)

    def get_name(self) -> str:
        """
        Get note formatter name.

        Returns:
            Formatter name
        """
        return "OKF"

    async def generate_n_format_note_content(self, processed_data: SummarizerResult) -> Optional[Path]:
        """
        Generate an OKF-formatted note from processed data.

        Args:
            processed_data: SummarizerResult containing structured note data

        Returns:
            Note path if successful
        """
        self._logger.info(f"OKF note: summary result {processed_data}")
        if not self._setting.get_vault_path():
            return None

        title = processed_data.title if processed_data.title else "untitled_note"

        # Create safe filename
        safe_filename = self._create_safe_filename(title)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{safe_filename}.md"

        # Determine the folder path
        formatter_folder = "okf"
        lang_folder = processed_data.language
        category_folder = processed_data.category.lower().replace(" ", "_")

        # Ensure vault_path is a Path object
        vault_path = Path(self._setting.get_vault_path())
        note_dir = vault_path / formatter_folder / lang_folder / category_folder
        note_dir.mkdir(parents=True, exist_ok=True)

        note_path = Path(note_dir / filename)

        # Generate note content
        content = self._generate_note_content(processed_data)

        # Write the note
        with open(note_path, "w", encoding="utf-8") as f:
            f.write(content)

        self._logger.info(f"Created OKF note: {note_path}")

        return note_path

    def _generate_note_content(self, data: SummarizerResult) -> str:
        """
        Generate the full note content using Jinja2 template.

        Args:
            data: Processed note data

        Returns:
            Complete note content as string
        """
        # Prepare template context
        context = {
            "title": data.title if data.title else "untitled_note",
            "channel": data.channel if data.channel else "http",
            "category": data.category if data.category else "jot",
            "language": data.language if data.language else "ar",
            "created": datetime.now().isoformat(),
            "summary": data.summary if data.summary else "",
            "content": data.content if data.content else "",
            "concepts": data.concepts if data.concepts else "",
            "entities": data.entities if data.entities else {},
            "original_text": data.content if data.content else "",
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

        # Include metadata
        if data.metadata:
            for k, v in data.metadata:
                context[k] = v

        # Render template
        template = self._env.get_template("okf.md.j2")
        return template.render(**context)

    def _create_safe_filename(self, title: str) -> str:
        """Create a safe filename from a title."""
        # Use the safe_filename filter
        return CUSTOM_FILTERS['safe_filename'](title)

