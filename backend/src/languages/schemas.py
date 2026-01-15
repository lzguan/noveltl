from pydantic import BaseModel


class Language(BaseModel):
    """
    Pydantic schema for language.

    Attributes:
        code: String code key to language.
        name: String name of language.
    """
    code: str
    name: str
