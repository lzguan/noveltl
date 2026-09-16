from typing import Literal

from pydantic import Field, SecretStr

from src.config import BaseConfig


class FileStoreSettings(BaseConfig):
    """Configuration for the application's default S3-compatible store."""

    FILE_STORE_NAME: str = Field(default="default", min_length=1, max_length=32)
    S3_ENDPOINT_URL: str | None = None
    S3_BUCKET: str = Field(default="noveltl", min_length=1, max_length=255)
    S3_REGION: str = Field(default="garage", min_length=1)
    S3_ADDRESSING_STYLE: Literal["auto", "path", "virtual"] = "path"
    AWS_ACCESS_KEY_ID: str | None = Field(default=None, min_length=1)
    AWS_SECRET_ACCESS_KEY: SecretStr | None = None


file_store_settings = FileStoreSettings()
