from ..schemas import Model


class Language(Model):
    """
    Pydantic schema for language.

    Attributes:
        language_code: String code key to language.
        language_name: String name of language.
    """

    language_code: str
    language_name: str
