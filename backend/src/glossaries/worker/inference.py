import json
import logging
import os
from typing import Any

from .interfaces import TranslationModel

logger = logging.getLogger(__name__)

GLOSSARY_TRANSLATION_API_BASE_URL = os.environ.get("GLOSSARY_TRANSLATION_API_BASE_URL", "https://api.openai.com/v1")
GLOSSARY_TRANSLATION_API_KEY = os.environ.get("GLOSSARY_TRANSLATION_API_KEY", "")
GLOSSARY_TRANSLATION_MODEL = os.environ.get("GLOSSARY_TRANSLATION_MODEL", "gpt-4o-mini")

BATCH_SIZE = 50

SYSTEM_PROMPT = (
    "You are a professional translator specializing in novel translation. "
    "You will be given a JSON array of terms from a novel in {source_lang}. "
    "Translate each term into {target_lang}. "
    "Maintain consistency: the same term should always have the same translation. "
    "For character names, transliterate or adapt them appropriately for the target language. "
    "Return ONLY a JSON array of translated strings in the same order as the input, with no extra text."
)


class OpenAITranslationModel(TranslationModel):
    """
    Translation model using the OpenAI-compatible chat completions API.

    Configurable via environment variables:
        GLOSSARY_TRANSLATION_API_BASE_URL: Base URL for the API (default: OpenAI).
        GLOSSARY_TRANSLATION_API_KEY: API key for authentication.
        GLOSSARY_TRANSLATION_MODEL: Model name to use (default: gpt-4o-mini).
    """

    def __init__(
        self,
        api_base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        batch_size: int = BATCH_SIZE,
    ) -> None:
        from openai import OpenAI  # type: ignore[import-untyped]

        self.api_base_url = api_base_url or GLOSSARY_TRANSLATION_API_BASE_URL
        self.api_key = api_key or GLOSSARY_TRANSLATION_API_KEY
        self.model = model or GLOSSARY_TRANSLATION_MODEL
        self.batch_size = batch_size
        self.client: Any = OpenAI(base_url=self.api_base_url, api_key=self.api_key)

    def translate(self, source_terms: list[str], source_lang: str, target_lang: str) -> list[str]:
        """
        Translate source_terms in batches. On per-batch failure, fill with original terms.
        """
        all_translated: list[str] = []

        for i in range(0, len(source_terms), self.batch_size):
            batch = source_terms[i : i + self.batch_size]
            try:
                translated_batch = self._translate_batch(batch, source_lang, target_lang)
                all_translated.extend(translated_batch)
            except Exception:
                logger.exception(
                    "Translation batch failed (offset %d, size %d). Falling back to original terms.", i, len(batch)
                )
                all_translated.extend(batch)

        return all_translated

    def _translate_batch(self, terms: list[str], source_lang: str, target_lang: str) -> list[str]:
        """
        Translate a single batch of terms via the chat completions API.

        Raises:
            Exception: On API or parsing errors.
        """
        system_msg = SYSTEM_PROMPT.format(source_lang=source_lang, target_lang=target_lang)
        user_msg = json.dumps(terms, ensure_ascii=False)

        response: Any = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
        )

        content: str | None = response.choices[0].message.content
        if content is None:
            raise ValueError("Empty response from translation API")

        # Strip markdown code fences if present
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            # Remove first and last lines (the fences)
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)

        parsed: list[str] = json.loads(content)

        if len(parsed) != len(terms):
            logger.warning(
                "Translation API returned %d results for %d terms. Padding/truncating.",
                len(parsed),
                len(terms),
            )
            # Pad with originals or truncate
            if len(parsed) < len(terms):
                parsed.extend(terms[len(parsed) :])
            else:
                parsed = parsed[: len(terms)]

        return parsed
