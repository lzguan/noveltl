"""This module provides global config variables."""

import logging
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

uvicorn_logger = logging.getLogger("uvicorn.info")


class BaseConfig(BaseSettings):
    """Base config class."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class DatabaseSettings(BaseConfig):
    """Settings class for global config variables."""

    DB_HOST: str = Field(default="", min_length=1)
    DB_USER: str = Field(default="", min_length=1)
    DB_PASSWORD: str = Field(default="", min_length=1)
    DB_NAME: str = Field(default="", min_length=1)
    DB_URL: str = Field(default="", min_length=1)


class AuthSettings(BaseConfig):
    """Settings class for authentication config variables."""

    SECRET_KEY: str = Field(default="", min_length=1)


class RedisSettings(BaseConfig):
    """Settings class for redis config variables."""

    REDIS_HOST: str = Field(default="", min_length=1)
    REDIS_PORT: int = Field(default=6379, gt=0)

    FILTERS_DATABASE: int = Field(default=0, ge=0)
    AUTOLABELS_DATABASE: int = Field(default=1, ge=0)
    REQUESTS_DATABASE: int = Field(default=2, ge=0)
    AGENT_DATABASE: int = Field(default=3, ge=0)


class LogSettings(BaseConfig):
    """Settings class for logging config variables."""

    LOG_LEVEL: Literal["INFO", "WARNING", "ERROR", "DEBUG"] = Field(default="INFO", min_length=1)
    LOG_OUTPUT: Literal["FILE", "STREAM", "BOTH"] = Field(default="BOTH", min_length=1)
    LOG_OUTPUT_FILE: str = Field(default="logs/backend.log", min_length=1)


database_settings = DatabaseSettings()
auth_settings = AuthSettings()
redis_settings = RedisSettings()
log_settings = LogSettings()
