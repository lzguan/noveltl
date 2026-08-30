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


class FactCategory(StrEnum):
    GENDER = "gender"
    AGE_STAGE = "age_stage"
    SPECIES = "species"
    APPEARANCE = "appearance"
    CULTIVATION_LEVEL = "cultivation_level"
    TRAIT = "trait"
    ABILITY = "ability"
    LIMITATION = "limitation"


class RelationCategory(StrEnum):
    ALIAS = "alias"
    KINSHIP = "kinship"
    FRIENDSHIP = "friendship"
    ROMANCE = "romance"
    MENTORSHIP = "mentorship"
    RANK = "rank"
    MEMBERSHIP = "membership"
    SERVICE = "service"
    OWNERSHIP = "ownership"
    ALLIANCE = "alliance"
    RIVALRY = "rivalry"
    ORGANIZATIONAL_HIERARCHY = "organizational_hierarchy"
    COMMERCIAL_PARTNERSHIP = "commercial_partnership"
