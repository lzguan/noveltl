"""This module provides global config variables."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class BaseConfig(BaseSettings):
    """Base config class."""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

class DatabaseSettings(BaseConfig):
    """Settings class for global config variables."""
    DB_HOST : str = Field(default="", min_length=1)
    DB_PORT : str = Field(default="", min_length=1)
    DB_USER : str = Field(default="", min_length=1)
    DB_PASSWORD : str = Field(default="", min_length=1)
    DB_NAME : str = Field(default="", min_length=1)
    DB_URL : str = Field(default="", min_length=1)

class AuthSettings(BaseConfig):
    """Settings class for authentication config variables."""
    SECRET_KEY : str = Field(default="", min_length=1)

database_settings = DatabaseSettings()
auth_settings = AuthSettings()