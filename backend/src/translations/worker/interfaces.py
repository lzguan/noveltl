from typing import Protocol


class ChapterTranslationModel(Protocol):
    """
    Abstract interface for a chapter translation model.

    Implementations must accept full chapter text (or a chunk thereof),
    source/target language codes, and an optional glossary for terminology
    consistency, then return the translated text.
    """

    def translate(
        self,
        source_text: str,
        source_lang: str,
        target_lang: str,
        glossary_entries: list[tuple[str, str]] | None = None,
    ) -> str:
        """
        Translate source text from source_lang to target_lang.

        Args:
            source_text: The chapter text to translate.
            source_lang: ISO 639-1 source language code.
            target_lang: ISO 639-1 target language code.
            glossary_entries: Optional list of (source_term, translated_term) pairs
                for terminology consistency.

        Returns:
            The translated text.

        Raises:
            Exception: On API or processing errors (callers handle failure).
        """
        ...
