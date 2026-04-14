"""This module provides global config variables."""

import logging

from arq.connections import RedisSettings
from pydantic import Field  # type: ignore
from pydantic_settings import BaseSettings, SettingsConfigDict  # type: ignore

uvicorn_logger = logging.getLogger("uvicorn.info")

class BaseConfig(BaseSettings):
    """Base config class."""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

class DatabaseSettings(BaseConfig):
    """Settings class for global config variables."""
    DB_HOST : str = Field(default="", min_length=1)
    DB_USER : str = Field(default="", min_length=1)
    DB_PASSWORD : str = Field(default="", min_length=1)
    DB_NAME : str = Field(default="", min_length=1)
    DB_URL : str = Field(default="", min_length=1)

class AuthSettings(BaseConfig):
    """Settings class for authentication config variables."""
    SECRET_KEY : str = Field(default="", min_length=1)

class _RedisSettings(BaseConfig):
    """Settings class for redis config variables."""
    REDIS_HOST : str = Field(default="", min_length=1)
    REDIS_PORT : int = Field(default=6379, gt=0)

database_settings = DatabaseSettings()
auth_settings = AuthSettings()
_redis_settings = _RedisSettings()
redis_settings = RedisSettings(host=_redis_settings.REDIS_HOST, port=_redis_settings.REDIS_PORT)
