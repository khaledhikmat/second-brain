import os
from pathlib import Path

class EnvVarsSettingService:
    def __init__(self):
        # Initialize with environment variables or default values
        pass

    def get_logs_path(self) -> Path:
        # read from env variables or return a default path
        return Path(os.getenv("LOGS_PATH", "/logs"))
    
    def get_database_url(self) -> str:
        # read from env variables or return a default database URL
        return os.getenv("DATABASE_URL", "sqlite:///default.db")
    
    def get_database_echo(self) -> bool:
        # read from env variables or return a default value
        return os.getenv("DATABASE_ECHO", "False").lower() in ("true", "1", "t")
