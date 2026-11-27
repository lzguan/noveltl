from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ReaderSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    READER_DB_URL: str = Field(
        default="postgresql+psycopg://reader:reader@reader_db:5432/reader",
        min_length=1,
    )
    READER_TEST_DB_URL: str = Field(default="")
    READER_PUBLIC_BASE_URL: str = Field(default="http://localhost:5174", min_length=1)
    READER_INSTANCE_NAME: str = Field(default="NovelTL Reader", min_length=1)
    READER_ADMIN_USERNAME: str = Field(default="")
    READER_ADMIN_PASSWORD_HASH: str = Field(default="")
    READER_ADMIN_SECRET: str = Field(default="")
    READER_ADMIN_TOKEN_TTL_SECONDS: int = Field(default=86400, ge=60)

    @property
    def normalized_public_base_url(self) -> str:
        return self.READER_PUBLIC_BASE_URL.rstrip("/")

    @property
    def is_admin_configured(self) -> bool:
        return bool(
            self.READER_ADMIN_USERNAME.strip()
            and self.READER_ADMIN_PASSWORD_HASH.strip()
            and self.READER_ADMIN_SECRET.strip()
        )


reader_settings = ReaderSettings()


def novel_public_url(novel_id: object) -> str:
    return f"{reader_settings.normalized_public_base_url}/novel/{novel_id}"
