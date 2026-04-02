from enum import IntEnum, StrEnum

MAX_NOVEL_TITLE_LEN = 255
MAX_CHAPTER_TITLE_LEN = 255
MAX_AUTHOR_LENGTH = 31


class Visibility(IntEnum):
    PRIVATE = 0
    RESTRICTED = 1
    UNLISTED = 2
    PUBLIC = 3


class Role(StrEnum):
    OWNER = "owner"
    VIEWER = "viewer"
    EDITOR = "editor"


class NovelType(StrEnum):
    ORIGINAL = "original"
    TRANSLATION = "translation"
    OTHER = "other"


class AssociationType(StrEnum):
    TRANSLATION = "translation"
