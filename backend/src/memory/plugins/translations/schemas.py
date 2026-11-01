from src.memory.types import ReviewStatus
from src.schemas import Model


class TermTranslation(Model):
    """A canonical rendering for one exact source form in the group's language."""

    term: str
    translation: str
    review_status: ReviewStatus
