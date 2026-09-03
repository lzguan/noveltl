from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, get_args

type ModelName = Literal["deepseek:deepseek-v4-flash-none", "deepseek:deepseek-v4-flash-low"]
MODEL_NAMES: tuple[ModelName, ...] = get_args(ModelName.__value__)
type ToolsetName = Literal[
    "glossary_terms",
    "glossary_definitions_read",
    "glossary_definitions_write",
    "glossary_relations_read",
    "glossary_relations_write",
    "glossary_facts_read",
    "glossary_facts_write",
    "glossary_gender_read",
    "glossary_gender_write",
    "glossary_gender_advanced_facts_read",
    "glossary_gender_advanced_facts_write",
    "glossary_events_read",
    "glossary_events_write",
    "glossary_gender_advanced_events_read",
    "glossary_gender_advanced_events_write",
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


@dataclass(frozen=True)
class ToolsetRequires:
    toolset: ToolsetName
    requirement: ToolsetName


@dataclass(frozen=True)
class ToolsetExcludes:
    toolset1: ToolsetName
    toolset2: ToolsetName


type ToolsetRestriction = ToolsetRequires | ToolsetExcludes


TOOLSET_METADATA: tuple[ToolsetMetadata, ...] = (
    ToolsetMetadata("glossary_terms", "Glossary terms", "Create and classify source-language terms.", "memory"),
    ToolsetMetadata(
        "glossary_definitions_read",
        "Glossary definitions: read",
        "Retrieve canonical term meanings.",
        "memory",
    ),
    ToolsetMetadata(
        "glossary_definitions_write",
        "Glossary definitions: write",
        "Create, supersede, or expire canonical term meanings.",
        "memory",
    ),
    ToolsetMetadata(
        "glossary_relations_read",
        "Glossary relations: read",
        "Retrieve categorized relationships.",
        "memory",
    ),
    ToolsetMetadata(
        "glossary_relations_write",
        "Glossary relations: write",
        "Create, supersede, or expire categorized relationships.",
        "memory",
    ),
    ToolsetMetadata(
        "glossary_facts_read",
        "Glossary facts: read",
        "Retrieve continuity-critical attributes other than gender.",
        "memory",
    ),
    ToolsetMetadata(
        "glossary_facts_write",
        "Glossary facts: write",
        "Create, supersede, or expire continuity-critical attributes other than gender.",
        "memory",
    ),
    ToolsetMetadata(
        "glossary_gender_read",
        "Glossary gender: read",
        "Retrieve explicitly established gender-related state.",
        "memory",
    ),
    ToolsetMetadata(
        "glossary_gender_write",
        "Glossary gender: write",
        "Create, supersede, or expire explicitly established gender-related state.",
        "memory",
    ),
    ToolsetMetadata(
        "glossary_gender_advanced_facts_read",
        "Advanced gender facts: read",
        "Retrieve current physical body and self-identity state separately.",
        "memory",
    ),
    ToolsetMetadata(
        "glossary_gender_advanced_facts_write",
        "Advanced gender facts: write",
        "Maintain one current body and identity state per person.",
        "memory",
    ),
    ToolsetMetadata(
        "glossary_events_read",
        "Glossary events: read",
        "Retrieve consequential occurrences.",
        "memory",
    ),
    ToolsetMetadata(
        "glossary_events_write",
        "Glossary events: write",
        "Create or supersede consequential occurrences.",
        "memory",
    ),
    ToolsetMetadata(
        "glossary_gender_advanced_events_read",
        "Advanced gender events: read",
        "Retrieve categorized transformations, reveals, possessions, swaps, and disguises.",
        "memory",
    ),
    ToolsetMetadata(
        "glossary_gender_advanced_events_write",
        "Advanced gender events: write",
        "Record categorized consequential gender-related occurrences.",
        "memory",
    ),
    ToolsetMetadata(
        "glossary_gender_transformation",
        "Gender transformation guidance",
        "Distinguish persistent changes, reveals, disguises, bodies, and avatars.",
        "guidance",
    ),
    ToolsetMetadata(
        "glossary_cultivation",
        "Cultivation guidance",
        "Track durable cultivation levels without recording temporary boosts.",
        "guidance",
    ),
    ToolsetMetadata(
        "glossary_system",
        "System guidance",
        "Track durable system mechanics, unlocks, and meaningful state.",
        "guidance",
    ),
    ToolsetMetadata(
        "glossary_artifacts",
        "Artifact guidance",
        "Track recurring fantastical objects, their functions, and lasting changes.",
        "guidance",
    ),
)

TOOLSET_RESTRICTIONS: tuple[ToolsetRestriction, ...] = (
    ToolsetRequires("glossary_definitions_write", "glossary_definitions_read"),
    ToolsetRequires("glossary_relations_write", "glossary_relations_read"),
    ToolsetRequires("glossary_facts_write", "glossary_facts_read"),
    ToolsetRequires("glossary_gender_write", "glossary_gender_read"),
    ToolsetRequires("glossary_gender_advanced_facts_write", "glossary_gender_advanced_facts_read"),
    ToolsetRequires("glossary_events_write", "glossary_events_read"),
    ToolsetRequires("glossary_gender_advanced_events_write", "glossary_gender_advanced_events_read"),
    ToolsetRequires("glossary_gender_transformation", "glossary_gender_advanced_facts_read"),
    ToolsetRequires("glossary_gender_transformation", "glossary_gender_advanced_facts_write"),
    ToolsetRequires("glossary_gender_transformation", "glossary_relations_read"),
    ToolsetRequires("glossary_gender_transformation", "glossary_relations_write"),
    ToolsetRequires("glossary_cultivation", "glossary_facts_read"),
    ToolsetRequires("glossary_cultivation", "glossary_facts_write"),
    ToolsetRequires("glossary_system", "glossary_facts_read"),
    ToolsetRequires("glossary_system", "glossary_facts_write"),
    ToolsetRequires("glossary_artifacts", "glossary_definitions_read"),
    ToolsetRequires("glossary_artifacts", "glossary_definitions_write"),
    ToolsetExcludes("glossary_gender_read", "glossary_gender_advanced_facts_read"),
    ToolsetExcludes("glossary_events_read", "glossary_gender_advanced_events_read"),
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
    for restriction in TOOLSET_RESTRICTIONS:
        match restriction:
            case ToolsetRequires(toolset=name, requirement=requirement):
                if name in selected and requirement not in selected:
                    raise ValueError(f"Toolset {name} requires: {requirement}")
            case ToolsetExcludes(toolset1=toolset1, toolset2=toolset2):
                if toolset1 in selected and toolset2 in selected:
                    raise ValueError(f"Toolsets {toolset1} and {toolset2} cannot be selected together")
