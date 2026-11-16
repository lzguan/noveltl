from functools import cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SeedSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    EVALS_DB_URL: str = Field(min_length=1)


@cache
def seed_settings() -> SeedSettings:
    return SeedSettings()
