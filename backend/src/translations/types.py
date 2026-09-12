from enum import StrEnum


class TranslationTaskStatus(StrEnum):
    WAITING = "waiting"
    READY = "ready"
    PREPARING = "preparing"
    PREPARED = "prepared"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"
