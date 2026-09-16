from src.config import BaseConfig


class QwenSettings(BaseConfig):
    """Settings for the Qwen model."""

    QWEN_API_KEY: str
    QWEN_API_URL: str


qwen_settings = QwenSettings()
