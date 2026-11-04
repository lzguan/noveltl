from enum import StrEnum


class ConventionCategory(StrEnum):
    """Which translation step a convention guides."""

    NAMING = "naming"
    STYLE = "style"
