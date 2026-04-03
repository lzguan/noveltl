import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

NOVEL_TRANSLATION_API_BASE_URL = os.environ.get("NOVEL_TRANSLATION_API_BASE_URL", "https://api.openai.com/v1")
NOVEL_TRANSLATION_API_KEY = os.environ.get("NOVEL_TRANSLATION_API_KEY", "")
NOVEL_TRANSLATION_MODEL = os.environ.get("NOVEL_TRANSLATION_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = (
    "You are a professional novel translator. "
    "Translate the following text from {source_lang} to {target_lang}. "
    "Preserve the original formatting, paragraph breaks, and literary style. "
    "Do not add any commentary, notes, or explanations — return ONLY the translated text."
)

GLOSSARY_SECTION = (
    "\n\nUse the following glossary for consistent terminology. "
    "Always use these translations when the source terms appear:\n{entries}"
)


class OpenAIChapterTranslationModel:
    """
    Chapter translation model using the OpenAI-compatible chat completions API.

    Configurable via environment variables:
        NOVEL_TRANSLATION_API_BASE_URL: Base URL for the API (default: OpenAI).
        NOVEL_TRANSLATION_API_KEY: API key for authentication.
        NOVEL_TRANSLATION_MODEL: Model name to use (default: gpt-4o-mini).
    """

    def __init__(
        self,
        api_base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        from openai import OpenAI  # type: ignore[import-untyped]

        self.api_base_url = api_base_url or NOVEL_TRANSLATION_API_BASE_URL
        self.api_key = api_key or NOVEL_TRANSLATION_API_KEY
        self.model = model or NOVEL_TRANSLATION_MODEL
        self.client: Any = OpenAI(base_url=self.api_base_url, api_key=self.api_key)

    def translate(
        self,
        source_text: str,
        source_lang: str,
        target_lang: str,
        glossary_entries: list[tuple[str, str]] | None = None,
    ) -> str:
        """
        Translate source_text using the chat completions API.

        Raises on API or response errors — callers are responsible for
        catching exceptions and updating job status.
        """
        system_msg = SYSTEM_PROMPT.format(source_lang=source_lang, target_lang=target_lang)

        if glossary_entries:
            formatted_entries = "\n".join(f"  {src} \u2192 {tgt}" for src, tgt in glossary_entries)
            system_msg += GLOSSARY_SECTION.format(entries=formatted_entries)

        response: Any = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": source_text},
            ],
            temperature=0.3,
        )

        content: str | None = response.choices[0].message.content
        if content is None:
            raise ValueError("Empty response from translation API")

        return content.strip()
