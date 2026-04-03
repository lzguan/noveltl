from typing import Protocol


class TranslationModel(Protocol):
    """
    Abstract class for a translation model used in glossary translation jobs.
    """

    def translate(self, source_terms: list[str], source_lang: str, target_lang: str) -> list[str]:
        """
        Translate a list of source terms from source_lang to target_lang.

        Args:
            source_terms: List of terms to translate.
            source_lang: ISO 639-1 source language code.
            target_lang: ISO 639-1 target language code.

        Returns:
            A list of translated terms, one per input term. If a term cannot be
            translated, the original term is returned in its place.
        """
        ...
