from decimal import Decimal
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = str


class EvalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InclusiveChapterRange(EvalModel):
    start_inclusive: int = Field(ge=1)
    end_inclusive: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if self.end_inclusive < self.start_inclusive:
            raise ValueError("end_inclusive must not be less than start_inclusive")
        return self


class ExpectedMemory(EvalModel):
    id: Identifier = Field(min_length=1, pattern=r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
    memory_type: str = Field(min_length=1)
    category: str | None = Field(default=None, min_length=1)
    terms: list[str] = Field(default_factory=list)
    content: str = Field(min_length=1)
    expected_state: Literal["active", "ended"] = "active"
    lifecycle: Literal["any", "create", "supersede", "expire"] = "any"

    @model_validator(mode="after")
    def validate_terms(self) -> Self:
        if any(not term.strip() for term in self.terms):
            raise ValueError("terms must not contain empty values")
        if len(self.terms) != len(set(self.terms)):
            raise ValueError("terms must not contain duplicates")
        return self


class Checkpoint(EvalModel):
    id: Identifier = Field(min_length=1, pattern=r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
    corpus: Identifier = Field(min_length=1)
    chapters: InclusiveChapterRange
    activity: Literal["normal", "busy", "quiet"] = "normal"
    expected_memories: list[ExpectedMemory] = Field(default_factory=list)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_memory_ids(self) -> Self:
        ids = [memory.id for memory in self.expected_memories]
        if len(ids) != len(set(ids)):
            raise ValueError("expected memory IDs must be unique within a checkpoint")
        return self


class ToolsetSpec(EvalModel):
    name: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    settings: dict[str, Any] = Field(default_factory=dict)


class AgentSpec(EvalModel):
    profile: str = Field(min_length=1)
    toolsets: list[ToolsetSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_toolset_names(self) -> Self:
        names = [toolset.name for toolset in self.toolsets]
        if len(names) != len(set(names)):
            raise ValueError("toolset names must be unique")
        return self


class ExecutionSpec(EvalModel):
    replicas: int = Field(default=1, ge=1)
    max_parallel: int = Field(default=1, ge=1)
    retries_per_chapter: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_parallelism(self) -> Self:
        if self.max_parallel > self.replicas:
            raise ValueError("max_parallel must not exceed replicas")
        return self


class BudgetSpec(EvalModel):
    max_cost_usd: Decimal | None = Field(default=None, gt=Decimal("0"))
    max_wall_seconds: int | None = Field(default=None, gt=0)


class RunConfig(EvalModel):
    id: Identifier = Field(min_length=1, pattern=r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
    change: str = Field(min_length=1)
    objectives: list[str] = Field(min_length=1)
    expected_side_effects: list[str] = Field(default_factory=list)
    degradation_guardrails: list[str] = Field(min_length=1)
    decision_rule: str = Field(min_length=1)
    corpus: Identifier = Field(min_length=1)
    chapters: InclusiveChapterRange
    checkpoint_sets: list[Identifier] = Field(default_factory=list)
    agent: AgentSpec
    execution: ExecutionSpec = Field(default_factory=ExecutionSpec)
    budget: BudgetSpec = Field(default_factory=BudgetSpec)
