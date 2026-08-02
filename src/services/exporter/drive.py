import io
import json

from services.setting.typex import ISettingService
from services.logger.typex import ILoggerService

_DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class GoogleDriveExporterService:
    """
    Uploads markdown files to a Google Drive folder using OAuth user credentials.
    Service accounts cannot write to personal Drive (no storage quota).
    Run src/auth_drive.py once locally to obtain the token.
    Auth priority: GOOGLE_DRIVE_OAUTH_TOKEN_JSON (env string, Railway)
               -> GOOGLE_DRIVE_TOKEN_FILE (local file path, dev).
    """

    def __init__(self, setting: ISettingService, logger: ILoggerService):
        self._logger = logger
        self._folder_id = setting.get_google_drive_folder_id()
        self._service = None

        token_json = setting.get_google_drive_oauth_token_json().strip()
        token_file = setting.get_google_drive_token_file().strip()

        if token_json:
            self._service = self._build_from_token_json(token_json)
        elif token_file:
            self._service = self._build_from_token_file(token_file)

    def is_configured(self) -> bool:
        return self._service is not None and bool(self._folder_id)

    def upload(self, filename: str, content: bytes) -> None:
        """Upload or replace a file in the configured Drive folder."""
        from googleapiclient.http import MediaIoBaseUpload

        media = MediaIoBaseUpload(
            io.BytesIO(content), mimetype="text/markdown", resumable=False
        )

        existing_id = self._find_existing(filename)
        if existing_id:
            self._service.files().update(
                fileId=existing_id, media_body=media
            ).execute()
            self._logger.info(f"Drive: updated '{filename}' (id={existing_id})")
        else:
            self._service.files().create(
                body={"name": filename, "parents": [self._folder_id]},
                media_body=media,
            ).execute()
            self._logger.info(f"Drive: created '{filename}'")

    # ------------------------------------------------------------------
    def _find_existing(self, filename: str) -> str | None:
        # Single-quote the filename to avoid Drive query injection
        safe_name = filename.replace("'", "\\'")
        query = f"name='{safe_name}' and '{self._folder_id}' in parents and trashed=false"
        res = self._service.files().list(q=query, fields="files(id)").execute()
        files = res.get("files", [])
        return files[0]["id"] if files else None

    def _build_from_token_json(self, token_json: str):
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            info = json.loads(token_json)
            creds = Credentials.from_authorized_user_info(info, _DRIVE_SCOPES)
            creds = self._refresh_if_needed(creds)
            return build("drive", "v3", credentials=creds, cache_discovery=False)
        except Exception as e:
            self._logger.error(f"Drive: failed to init from token JSON: {e}")
            return None

    def _build_from_token_file(self, token_file: str):
        try:
            from pathlib import Path
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            creds = Credentials.from_authorized_user_file(
                str(Path(token_file).expanduser()), _DRIVE_SCOPES
            )
            creds = self._refresh_if_needed(creds)
            return build("drive", "v3", credentials=creds, cache_discovery=False)
        except Exception as e:
            self._logger.error(f"Drive: failed to init from token file: {e}")
            return None

    def _refresh_if_needed(self, creds):
        if creds and creds.expired and creds.refresh_token:
            import google.auth.transport.requests
            creds.refresh(google.auth.transport.requests.Request())
        return creds
