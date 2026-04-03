from enum import StrEnum

MAX_MODEL_NAME_LEN = 128
MAX_LANGUAGE_CODE_LEN = 8


class NovelTranslationStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class ChapterTranslationStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"
