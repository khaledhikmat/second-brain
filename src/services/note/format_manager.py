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

        # Create safe filename
        safe_filename = _create_safe_filename(processed_data.title)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{safe_filename}.md"

        # Determine the folder path
        formatter_folder = "obs"
        lang_folder = processed_data.language
        daily_folder = datetime.now().strftime("%Y%m%d")

        # Ensure vault_path is a Path object
        vault_path = Path(self._setting.get_vault_path())
        note_dir = vault_path / formatter_folder / lang_folder / daily_folder
        note_dir.mkdir(parents=True, exist_ok=True)

        note_path = Path(note_dir / filename)

        # Generate note content
        content = self._generate_note_content(processed_data)

        # Write the note
        with open(note_path, "w", encoding="utf-8") as f:
            f.write(content)

        self._logger.info(f"Created note: {note_path}")

        # Update index.md and log.md
        _update_index_md(note_dir, processed_data.title, filename, processed_data.category, self._logger)
        _update_log_md(note_dir, processed_data.title, filename, processed_data.category, self._logger)

        return note_path

    def _generate_note_content(self, data: SummarizerResult) -> str:
        """
        Generate the full note content with frontmatter using Jinja2 template.

        Args:
            data: Processed note data

        Returns:
            Complete note content as string
        """
        channel = data.channel if data.channel else "telegram"
        category = data.category if data.category else "jot"

        # Prepare simplified frontmatter
        frontmatter = {
            "channel": channel,
            "category": category,
            "language": data.language if data.language else "en",
            "title": data.title,
            "created": datetime.now().isoformat(),
            "processed_at": data.processedAt if data.processedAt else datetime.now().isoformat(),
        }

        # Add Metadata URL to frontmatter if present
        if data.metadata:
            for key, val in data.metadata.items():
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
            "message": data.message if data.message else "",
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

        # Render template
        template = self._env.get_template("obsidian.md.j2")
        return template.render(**context)

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

        # Create safe filename
        safe_filename = _create_safe_filename(processed_data.title)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{safe_filename}.md"

        # Determine the folder path
        formatter_folder = "okf"
        lang_folder = processed_data.language
        daily_folder = datetime.now().strftime("%Y%m%d")

        # Ensure vault_path is a Path object
        vault_path = Path(self._setting.get_vault_path())
        note_dir = vault_path / formatter_folder / lang_folder / daily_folder
        note_dir.mkdir(parents=True, exist_ok=True)

        note_path = Path(note_dir / filename)

        # Generate note content
        content = self._generate_note_content(processed_data)

        # Write the note
        with open(note_path, "w", encoding="utf-8") as f:
            f.write(content)

        self._logger.info(f"Created OKF note: {note_path}")

        # Update index.md and log.md
        _update_index_md(note_dir, processed_data.title, filename, processed_data.category, self._logger)
        _update_log_md(note_dir, processed_data.title, filename, processed_data.category, self._logger)

        return note_path

    def _generate_note_content(self, data: SummarizerResult) -> str:
        """
        Generate the full note content using Jinja2 template.

        Args:
            data: Processed note data

        Returns:
            Complete note content as string
        """
        channel = data.channel if data.channel else "telegram"
        category = data.category if data.category else "jot"

        # Prepare simplified frontmatter
        frontmatter = {
            "channel": channel,
            "type": category,
            "language": data.language if data.language else "en",
            "title": data.title,
            "created": datetime.now().isoformat(),
            "processed_at": data.processedAt if data.processedAt else datetime.now().isoformat(),
        }

        # Add Metadata URL to frontmatter if present
        if data.metadata:
            for key, val in data.metadata.items():
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
            "message": data.message if data.message else "",
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

        # Render template
        template = self._env.get_template("okf.md.j2")
        return template.render(**context)

## COMMON FUNCTIONS #

def _create_safe_filename(title: str) -> str:
    """Create a safe filename from a title."""
    # Use the safe_filename filter
    return CUSTOM_FILTERS['safe_filename'](title)

def _update_index_md(note_dir: Path, title: str, filename: str, category: str, logger: ILoggerService) -> None:
    """
    Update or create index.md with categorized note links.

    Args:
        note_dir: Directory containing the notes
        title: Note title
        filename: Note filename
        category: Note category
        logger: Logger service
    """
    index_path = note_dir / "index.md"
    category = category if category else "Uncategorized"
    new_entry = f"- [{title}]({filename})"

    if index_path.exists():
        # Read existing content
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse to find category sections
        lines = content.split("\n")
        category_found = False
        insert_index = -1

        for i, line in enumerate(lines):
            if line.strip() == f"# {category}":
                category_found = True
                # Find where to insert (after the category header)
                insert_index = i + 1
                break

        if category_found:
            # Insert under existing category
            lines.insert(insert_index, new_entry)
        else:
            # Add new category section at the end
            if lines and lines[-1].strip():
                lines.append("")
            lines.append(f"# {category}")
            lines.append("")
            lines.append(new_entry)

        content = "\n".join(lines)
    else:
        # Create new index.md
        content = f"# {category}\n\n{new_entry}\n"

    # Write back
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"Updated index.md: {index_path}")

def _update_log_md(note_dir: Path, title: str, filename: str, category: str, logger: ILoggerService) -> None:
    """
    Update or create log.md with chronological creation entries.

    Args:
        note_dir: Directory containing the notes
        title: Note title
        filename: Note filename
        category: Note category
        logger: Logger service
    """
    log_path = note_dir / "log.md"
    today = datetime.now().strftime("%Y-%m-%d")
    new_entry = f"- **`{category}` Creation**: [{title}]({filename})"

    if log_path.exists():
        # Read existing content
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse to find today's date section
        lines = content.split("\n")
        date_found = False
        insert_index = -1

        for i, line in enumerate(lines):
            if line.strip() == f"## {today}":
                date_found = True
                # Insert after this date header
                insert_index = i + 1
                break

        if date_found:
            # Add under existing date section
            lines.insert(insert_index, new_entry)
        else:
            # Add new date section at the top (after "# Creation Log")
            # Find the header line
            header_index = -1
            for i, line in enumerate(lines):
                if line.strip() == "# Creation Log":
                    header_index = i
                    break

            if header_index != -1:
                # Insert new date section after header
                lines.insert(header_index + 1, "")
                lines.insert(header_index + 2, f"## {today}")
                lines.insert(header_index + 3, new_entry)
            else:
                # No header found, add at the beginning
                lines.insert(0, "# Creation Log")
                lines.insert(1, "")
                lines.insert(2, f"## {today}")
                lines.insert(3, new_entry)

        content = "\n".join(lines)
    else:
        # Create new log.md
        content = f"# Creation Log\n\n## {today}\n{new_entry}\n"

    # Write back
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"Updated log.md: {log_path}")

