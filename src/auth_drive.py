"""
One-time OAuth setup script for Google Drive access.

Run this ONCE locally to authorise the app with your Google account.
It will open a browser, ask you to log in and grant Drive access, then
save a token file that export.py uses on every subsequent run.

Usage:
    GOOGLE_DRIVE_OAUTH_CLIENT_SECRET_FILE=/path/to/client_secret.json \
    GOOGLE_DRIVE_TOKEN_FILE=~/.config/second-brain/drive_token.json \
    python3 src/auth_drive.py

After running, copy the token file contents into GOOGLE_DRIVE_OAUTH_TOKEN_JSON
in your Railway environment variables (single-line JSON).
"""
import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def main() -> None:
    from google_auth_oauthlib.flow import InstalledAppFlow

    client_secret_file = os.getenv("GOOGLE_DRIVE_OAUTH_CLIENT_SECRET_FILE", "")
    token_file = os.getenv(
        "GOOGLE_DRIVE_TOKEN_FILE",
        str(Path.home() / ".config" / "second-brain" / "drive_token.json"),
    )

    if not client_secret_file:
        print("ERROR: set GOOGLE_DRIVE_OAUTH_CLIENT_SECRET_FILE to your OAuth client secret JSON path")
        raise SystemExit(1)

    print(f"Using client secret: {client_secret_file}")
    print("A browser window will open. Log in with your Google account and grant Drive access.")

    flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, _SCOPES)
    creds = flow.run_local_server(port=0)

    # Save token file
    token_path = Path(token_file).expanduser()
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")

    print(f"\nToken saved to: {token_path}")
    print("\nSet this in your .env for local use:")
    print(f"  GOOGLE_DRIVE_TOKEN_FILE={token_path}")
    print("\nFor Railway, set GOOGLE_DRIVE_OAUTH_TOKEN_JSON to the following single-line value:")
    print(json.dumps(json.loads(token_path.read_text())))


if __name__ == "__main__":
    main()
