from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

type ModelName = Literal["deepseek:deepseek-v4-flash-none", "deepseek:deepseek-v4-flash-low"]
type ToolsetName = Literal[
    "glossary_terms",
    "glossary_definitions",
    "glossary_relations",
    "glossary_facts",
    "glossary_events",
    "glossary_gender",
    "glossary_gender_transformation",
    "glossary_cultivation",
    "glossary_system",
    "glossary_artifacts",
]

type ToolsetKind = Literal["memory", "guidance"]


@dataclass(frozen=True)
class ToolsetMetadata:
    name: ToolsetName
    label: str
    description: str
    kind: ToolsetKind
    requires: tuple[ToolsetName, ...] = ()


TOOLSET_METADATA: tuple[ToolsetMetadata, ...] = (
    ToolsetMetadata("glossary_terms", "Glossary terms", "Create and classify source-language terms.", "memory"),
    ToolsetMetadata("glossary_definitions", "Glossary definitions", "Maintain canonical term meanings.", "memory"),
    ToolsetMetadata("glossary_relations", "Glossary relations", "Maintain categorized relationships.", "memory"),
    ToolsetMetadata("glossary_facts", "Glossary facts", "Maintain continuity-critical attributes.", "memory"),
    ToolsetMetadata("glossary_events", "Glossary events", "Maintain consequential occurrences.", "memory"),
    ToolsetMetadata(
        "glossary_gender",
        "Gender guidance",
        "Track explicitly established gender for recurring people.",
        "guidance",
        ("glossary_facts",),
    ),
    ToolsetMetadata(
        "glossary_gender_transformation",
        "Gender transformation guidance",
        "Distinguish persistent changes, reveals, disguises, bodies, and avatars.",
        "guidance",
        ("glossary_gender", "glossary_facts"),
    ),
    ToolsetMetadata(
        "glossary_cultivation",
        "Cultivation guidance",
        "Track durable cultivation levels without recording temporary boosts.",
        "guidance",
        ("glossary_facts",),
    ),
    ToolsetMetadata(
        "glossary_system",
        "System guidance",
        "Track durable system mechanics, unlocks, and meaningful state.",
        "guidance",
        ("glossary_facts",),
    ),
    ToolsetMetadata(
        "glossary_artifacts",
        "Artifact guidance",
        "Track recurring fantastical objects, their functions, and lasting changes.",
        "guidance",
        ("glossary_definitions",),
    ),
)

TOOLSET_NAMES: tuple[ToolsetName, ...] = tuple(metadata.name for metadata in TOOLSET_METADATA)
TOOLSET_METADATA_BY_NAME: dict[str, ToolsetMetadata] = {
    metadata.name: metadata for metadata in TOOLSET_METADATA
}


def validate_toolset_selection(toolsets: Sequence[str]) -> None:
    if len(toolsets) != len(set(toolsets)):
        raise ValueError("toolsets must not contain duplicates")
    unknown = sorted(set(toolsets) - TOOLSET_METADATA_BY_NAME.keys())
    if unknown:
        raise ValueError(f"Unknown agent toolset(s): {', '.join(unknown)}")
    selected = set(toolsets)
    for name in toolsets:
        metadata = TOOLSET_METADATA_BY_NAME.get(name)
        if metadata is None:
            continue
        missing = [requirement for requirement in metadata.requires if requirement not in selected]
        if missing:
            raise ValueError(f"Toolset {name} requires: {', '.join(missing)}")
