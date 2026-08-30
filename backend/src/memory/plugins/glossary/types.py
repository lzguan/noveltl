from enum import StrEnum


class TermKind(StrEnum):
    PERSON = "person"
    PLACE = "place"
    ORGANIZATION = "organization"
    TECHNIQUE = "technique"
    ITEM = "item"
    CONCEPT = "concept"
    TITLE = "title"
    SPECIES = "species"
    OTHER = "other"

