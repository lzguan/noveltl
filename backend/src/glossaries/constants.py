from enum import StrEnum

MAX_GLOSSARY_NAME_LEN = 63
MAX_SOURCE_TERM_LEN = 128
MAX_TRANSLATED_TERM_LEN = 128
MAX_ENTITY_TYPE_LEN = 64
MAX_MODEL_NAME_LEN = 128


class GlossaryRole(StrEnum):
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class TranslationJobStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
