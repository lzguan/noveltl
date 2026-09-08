from dataclasses import dataclass
from typing import Annotated, Literal, get_args

from pydantic import ConfigDict, Field, model_validator

from src.schemas import Model

type ModelName = Literal["deepseek:deepseek-v4-flash-none", "deepseek:deepseek-v4-flash-low"]
MODEL_NAMES: tuple[ModelName, ...] = get_args(ModelName.__value__)
type ToolsetName = Literal[
    "continuity_summary",
    "glossary_terms",
    "glossary_definitions_read",
    "glossary_definitions_write",
    "glossary_relations_read",
    "glossary_relations_write",
    "glossary_aliases_write",
    "glossary_character_read",
    "glossary_character_write",
    "glossary_appearance_write",
    "glossary_cultivation_write",
    "glossary_gender_advanced_facts_write",
    "glossary_gender_advanced_relations_write",
    "glossary_events_read",
    "glossary_events_write",
    "glossary_gender_advanced_events_read",
    "glossary_gender_advanced_events_write",
    "glossary_gender_transformation",
    "glossary_artifacts",
]

type ToolsetKind = Literal["memory", "guidance"]


@dataclass(frozen=True)
class ModelMetadata:
    name: ModelName
    label: str
    description: str


MODEL_METADATA: tuple[ModelMetadata, ...] = (
    ModelMetadata(
        "deepseek:deepseek-v4-flash-none",
        "DeepSeek V4 Flash (No thinking)",
        "DeepSeek V4 Flash with thinking disabled.",
    ),
    ModelMetadata(
        "deepseek:deepseek-v4-flash-low",
        "DeepSeek V4 Flash (Low thinking)",
        "DeepSeek V4 Flash with low thinking effort.",
    ),
)


class ToolsetConfig(Model):
    """Base configuration for one enabled toolset."""

    model_config = ConfigDict(extra="forbid")


class OccurrenceRetentionConfig(ToolsetConfig):
    """Active-context retention for repeated occurrences per exact subject."""

    keep_first: Annotated[
        int,
        Field(
            ge=0,
            le=20,
            title="Keep first",
            description="Number of earliest occurrences to keep active per exact subject.",
        ),
    ] = 1
    keep_rolling: Annotated[
        int,
        Field(
            ge=0,
            le=20,
            title="Keep rolling",
            description="Size of the newest-occurrence FIFO window per exact subject.",
        ),
    ] = 3


@dataclass(frozen=True)
class ToolsetMetadata:
    name: ToolsetName
    label: str
    description: str
    kind: ToolsetKind
    default_enabled: bool = False
    config_model: type[ToolsetConfig] = ToolsetConfig


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
    ToolsetMetadata(
        "continuity_summary",
        "Continuity summary",
        "Carry a concise rolling handoff from the immediately preceding source chapter.",
        "memory",
    ),
    ToolsetMetadata(
        "glossary_terms",
        "Glossary terms",
        "Create and classify source-language terms.",
        "memory",
        default_enabled=True,
    ),
    ToolsetMetadata(
        "glossary_definitions_read",
        "Glossary definitions: read",
        "Retrieve canonical term meanings.",
        "memory",
        default_enabled=True,
    ),
    ToolsetMetadata(
        "glossary_definitions_write",
        "Glossary definitions: write",
        "Create, supersede, or expire canonical term meanings.",
        "memory",
        default_enabled=True,
    ),
    ToolsetMetadata(
        "glossary_relations_read",
        "Glossary relations: read",
        "Retrieve categorized relationships.",
        "memory",
        default_enabled=True,
    ),
    ToolsetMetadata(
        "glossary_relations_write",
        "Glossary relations: write",
        "Create, supersede, or expire categorized relationships.",
        "memory",
        default_enabled=True,
    ),
    ToolsetMetadata(
        "glossary_aliases_write",
        "Glossary aliases: write",
        "Create, supersede, or expire pairwise identity aliases.",
        "memory",
    ),
    ToolsetMetadata(
        "glossary_character_read",
        "Character state: read",
        "Retrieve character attributes across writer domains and observer perceptions.",
        "memory",
        default_enabled=True,
    ),
    ToolsetMetadata(
        "glossary_character_write",
        "Character core: write",
        "Maintain age stage, species, abilities, and limitations of individual characters.",
        "memory",
        default_enabled=True,
    ),
    ToolsetMetadata(
        "glossary_appearance_write",
        "Character appearance: write",
        "Maintain identifying physical attributes and recurring attire.",
        "memory",
        default_enabled=True,
    ),
    ToolsetMetadata(
        "glossary_cultivation_write",
        "Character cultivation: write",
        "Maintain completed cultivation levels separately for each track.",
        "memory",
    ),
    ToolsetMetadata(
        "glossary_gender_advanced_facts_write",
        "Character gender: write",
        "Maintain body, identity, presentation, and durable change rules.",
        "memory",
        default_enabled=True,
    ),
    ToolsetMetadata(
        "glossary_gender_advanced_relations_write",
        "Character gender perceptions: write",
        "Maintain directional beliefs about another person's gender.",
        "memory",
    ),
    ToolsetMetadata(
        "glossary_events_read",
        "Glossary events: read",
        "Retrieve consequential occurrences.",
        "memory",
        default_enabled=True,
    ),
    ToolsetMetadata(
        "glossary_events_write",
        "Glossary events: write",
        "Create or supersede consequential occurrences.",
        "memory",
        default_enabled=True,
    ),
    ToolsetMetadata(
        "glossary_gender_advanced_events_read",
        "Advanced gender events: read",
        "Retrieve categorized transformations, reveals, possessions, and body swaps.",
        "memory",
    ),
    ToolsetMetadata(
        "glossary_gender_advanced_events_write",
        "Advanced gender events: write",
        "Record categorized consequential gender-related occurrences.",
        "memory",
        config_model=OccurrenceRetentionConfig,
    ),
    ToolsetMetadata(
        "glossary_gender_transformation",
        "Gender transformation guidance",
        "Distinguish persistent changes, reveals, disguises, bodies, and avatars.",
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
    ToolsetRequires("glossary_aliases_write", "glossary_relations_read"),
    ToolsetRequires("glossary_character_write", "glossary_character_read"),
    ToolsetRequires("glossary_appearance_write", "glossary_character_read"),
    ToolsetRequires("glossary_cultivation_write", "glossary_character_read"),
    ToolsetRequires("glossary_gender_advanced_facts_write", "glossary_character_read"),
    ToolsetRequires("glossary_gender_advanced_relations_write", "glossary_character_read"),
    ToolsetRequires("glossary_events_write", "glossary_events_read"),
    ToolsetRequires("glossary_gender_advanced_events_write", "glossary_gender_advanced_events_read"),
    ToolsetRequires("glossary_gender_transformation", "glossary_character_read"),
    ToolsetRequires("glossary_gender_transformation", "glossary_gender_advanced_facts_write"),
    ToolsetRequires("glossary_gender_transformation", "glossary_gender_advanced_relations_write"),
    ToolsetRequires("glossary_artifacts", "glossary_definitions_read"),
    ToolsetRequires("glossary_artifacts", "glossary_definitions_write"),
)

TOOLSET_NAMES: tuple[ToolsetName, ...] = tuple(metadata.name for metadata in TOOLSET_METADATA)
TOOLSET_METADATA_BY_NAME: dict[str, ToolsetMetadata] = {metadata.name: metadata for metadata in TOOLSET_METADATA}

if tuple(metadata.name for metadata in MODEL_METADATA) != MODEL_NAMES:
    raise RuntimeError("Memory-agent model metadata does not match ModelName")


class ParsedToolsets(Model):
    """Selected memory-agent toolsets and their validated configurations."""

    model_config = ConfigDict(alias_generator=None, extra="forbid")

    continuity_summary: ToolsetConfig | None = None
    glossary_terms: ToolsetConfig | None = None
    glossary_definitions_read: ToolsetConfig | None = None
    glossary_definitions_write: ToolsetConfig | None = None
    glossary_relations_read: ToolsetConfig | None = None
    glossary_relations_write: ToolsetConfig | None = None
    glossary_aliases_write: ToolsetConfig | None = None
    glossary_character_read: ToolsetConfig | None = None
    glossary_character_write: ToolsetConfig | None = None
    glossary_appearance_write: ToolsetConfig | None = None
    glossary_cultivation_write: ToolsetConfig | None = None
    glossary_gender_advanced_facts_write: ToolsetConfig | None = None
    glossary_gender_advanced_relations_write: ToolsetConfig | None = None
    glossary_events_read: ToolsetConfig | None = None
    glossary_events_write: ToolsetConfig | None = None
    glossary_gender_advanced_events_read: ToolsetConfig | None = None
    glossary_gender_advanced_events_write: OccurrenceRetentionConfig | None = None
    glossary_gender_transformation: ToolsetConfig | None = None
    glossary_artifacts: ToolsetConfig | None = None

    def selected_names(self) -> tuple[ToolsetName, ...]:
        """Return enabled toolsets in canonical registry order."""
        return tuple(name for name in TOOLSET_NAMES if getattr(self, name) is not None)

    @model_validator(mode="after")
    def validate_restrictions(self) -> "ParsedToolsets":
        selected = set(self.selected_names())
        for restriction in TOOLSET_RESTRICTIONS:
            match restriction:
                case ToolsetRequires(toolset=name, requirement=requirement):
                    if name in selected and requirement not in selected:
                        raise ValueError(f"Toolset {name} requires: {requirement}")
                case ToolsetExcludes(toolset1=toolset1, toolset2=toolset2):
                    if toolset1 in selected and toolset2 in selected:
                        raise ValueError(f"Toolsets {toolset1} and {toolset2} cannot be selected together")
        return self


if set(ParsedToolsets.model_fields) != set(TOOLSET_NAMES):
    raise RuntimeError("ParsedToolsets fields do not match registered toolset names")

for metadata in TOOLSET_METADATA:
    field_annotation = ParsedToolsets.model_fields[metadata.name].annotation
    if metadata.config_model not in get_args(field_annotation):
        raise RuntimeError(f"Config model for {metadata.name} does not match ParsedToolsets")
