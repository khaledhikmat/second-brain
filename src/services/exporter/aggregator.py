from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import yaml

from services.setting.typex import ISettingService
from services.logger.typex import ILoggerService


class CategoryAggregatorService:
    """
    Scans vault/okf and produces one combined markdown per (language, category).
    Category is read from the 'type' frontmatter field written by OkfFormatManager.
    """

    def __init__(self, setting: ISettingService, logger: ILoggerService):
        self._setting = setting
        self._logger = logger

    def build_all(self) -> dict[tuple[str, str], str]:
        """
        Scan all OKF notes and return {(language, category): combined_markdown}.
        Skips index.md and log.md.  Sorts notes by 'created' ascending within each group.
        """
        vault_path = Path(self._setting.get_vault_path())
        okf_path = vault_path / "okf"

        if not okf_path.exists():
            self._logger.warning(f"OKF vault path not found: {okf_path}")
            return {}

        groups: dict[tuple[str, str], list] = {}

        for md_file in sorted(okf_path.rglob("*.md")):
            if md_file.name in ("index.md", "log.md"):
                continue

            note = self._parse_note(md_file)
            if note is None:
                continue

            language, category, title, created, body = note
            key = (language.lower(), category.lower())
            groups.setdefault(key, []).append((created, title, body))

        result: dict[tuple[str, str], str] = {}
        for (language, category), notes in sorted(groups.items()):
            notes.sort(key=lambda x: x[0])
            result[(language, category)] = self._build_combined_md(language, category, notes)
            self._logger.info(f"Aggregated {len(notes)} notes → {language.title()}-{category.title()}")

        return result

    def _parse_note(self, path: Path) -> Optional[tuple]:
        """Return (language, category, title, created, body) or None on parse failure."""
        try:
            text = path.read_text(encoding="utf-8")
            if not text.startswith("---"):
                return None
            parts = text.split("---", 2)
            if len(parts) < 3:
                return None

            fm = yaml.safe_load(parts[1]) or {}
            body = parts[2].strip()

            language = str(fm.get("language", "unknown"))
            # OKF uses 'type'; Obsidian uses 'category' — handle both for safety
            category = str(fm.get("type", fm.get("category", "unknown")))
            title = str(fm.get("title", path.stem))
            created = str(fm.get("created", ""))

            return language, category, title, created, body
        except Exception as e:
            self._logger.warning(f"Could not parse note {path.name}: {e}")
            return None

    def _build_combined_md(self, language: str, category: str, notes: list) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines = [
            f"# {language.title()} - {category.title()}",
            "",
            f"> _Combined knowledge base | {len(notes)} notes | Last updated: {timestamp}_",
            "",
        ]
        for created, title, body in notes:
            lines += [
                "---",
                "",
                f"## {title}",
                "",
            ]
            if created:
                lines += [f"_{created}_", ""]
            if body:
                lines += [body, ""]
        return "\n".join(lines)
