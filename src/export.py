"""
Export entry point — runs hourly as a cron job.
Aggregates OKF vault notes by (language, category) and writes each combined
markdown file to vault/exports/notebooklm/. If Google Drive is configured
(GOOGLE_DRIVE_OAUTH_TOKEN_JSON or GOOGLE_DRIVE_TOKEN_FILE), files are also
uploaded there to replace the previous version.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

from services.setting.envars import EnvVarsSettingService
from services.logger.dual import DualLoggerService
from services.exporter.aggregator import CategoryAggregatorService
from services.exporter.drive import GoogleDriveExporterService

load_dotenv()


def run_export() -> None:
    settings_service = EnvVarsSettingService()
    logger_service = DualLoggerService(settings_service)
    logger_service.info("Starting category export")

    try:
        aggregator = CategoryAggregatorService(settings_service, logger_service)
        aggregates = aggregator.build_all()

        if not aggregates:
            logger_service.info("No notes found in OKF vault. Nothing to export.")
            return

        # Always write to local exports directory
        exports_dir = Path(settings_service.get_vault_path()) / "exports" / "notebooklm"
        exports_dir.mkdir(parents=True, exist_ok=True)

        for (language, category), content in aggregates.items():
            filename = f"{language.title()}-{category.title()}.md"
            local_path = exports_dir / filename
            local_path.write_text(content, encoding="utf-8")
            logger_service.info(f"Written: {local_path}")

        logger_service.info(f"Export files written to: {exports_dir}")

        # Upload to Google Drive if configured (optional)
        drive_service = GoogleDriveExporterService(settings_service, logger_service)
        if drive_service.is_configured():
            logger_service.info(f"Uploading {len(aggregates)} files to Google Drive...")
            for (language, category), content in aggregates.items():
                filename = f"{language.title()}-{category.title()}.md"
                drive_service.upload(filename, content.encode("utf-8"))
            logger_service.info("Google Drive upload complete.")
        else:
            logger_service.info("Google Drive not configured — skipping upload.")

        logger_service.info("Export complete.")

    except Exception as e:
        logger_service.error(f"Export failed: {e}")
        raise


if __name__ == "__main__":
    run_export()
