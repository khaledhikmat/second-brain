import boto3
from botocore.config import Config

from services.setting.typex import ISettingService
from services.logger.typex import ILoggerService


class R2StorageService:
    def __init__(self, setting: ISettingService, logger: ILoggerService):
        self._logger = logger
        account_id = setting.get_r2_account_id()
        self._bucket = setting.get_r2_bucket_name()
        self._configured = bool(account_id)

        if self._configured:
            self._client = boto3.client(
                "s3",
                endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
                aws_access_key_id=setting.get_r2_access_key_id(),
                aws_secret_access_key=setting.get_r2_secret_access_key(),
                region_name="auto",
                config=Config(signature_version="s3v4"),
            )

    def is_configured(self) -> bool:
        return self._configured

    def upload(self, content: bytes, key: str) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=content)
        self._logger.info(f"Uploaded {len(content)} bytes to R2: {key}")

    def download(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read()
