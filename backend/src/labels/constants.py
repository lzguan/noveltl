from enum import StrEnum

MAX_LABEL_GROUP_NAME_LEN = 31
MAX_LABEL_ENTITY_GROUP_NAME_LEN = 64
MAX_LABEL_WORD_LEN = 128


class LabelRole(StrEnum):
    OWNER = "owner"
    VIEWER = "viewer"
    EDITOR = "editor"
