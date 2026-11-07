"""Conventions agent output and its writes.

Existing conventions are identified by handles (``c1``, ``c2``, ...) from
``MemAgentDeps.convention_handles``. Only pending, agent-created conventions are editable.
"""

from typing import Annotated, Self
from uuid import UUID

from pydantic import Field, StringConstraints, model_validator
from pydantic_ai import ModelRetry, RunContext

from src.memory.agent.dependencies import MemAgentDeps
from src.memory.exceptions import ConventionNotFoundException
from src.memory.plugins.conventions.access import create_convention, delete_convention, update_convention
from src.memory.plugins.conventions.types import ConventionCategory
from src.memory.types import Creator
from src.schemas import Model

type ConventionText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ConventionDraft(Model):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)] = Field(
        description="Short name for the convention."
    )
    rule: ConventionText = Field(description="The naming rule, with examples from this novel where helpful.")
    rationale: ConventionText | None = Field(default=None, description="Evidence for the rule.")


class ConventionRevision(ConventionDraft):
    handle: str = Field(description="Handle of an editable convention from the context, such as c3.")


class ConventionsOutput(Model):
    create: list[ConventionDraft] = Field(default_factory=list, description="New naming conventions.")
    revise: list[ConventionRevision] = Field(
        default_factory=list, description="Replacements for editable conventions, by handle."
    )
    withdraw: list[str] = Field(default_factory=list, description="Handles of editable conventions to remove.")

    @model_validator(mode="after")
    def each_handle_once(self) -> Self:
        handles = [revision.handle for revision in self.revise] + self.withdraw
        if len(handles) != len(set(handles)):
            raise ValueError("Revise or withdraw each convention handle at most once")
        return self


def write_conventions_output(ctx: RunContext[MemAgentDeps], output: ConventionsOutput) -> ConventionsOutput:
    """Write the agent's output in a savepoint, or discard it and request a correction.

    Output validator for the conventions agent. Revisions and withdrawals apply
    only to pending conventions created by an agent. Kept writes commit with the
    caller's transaction.

    Args:
        ctx: Run context holding the session, memory group, and convention handles.
        output: The agent's parsed output.

    Returns:
        The output, after it is written.

    Raises:
        ModelRetry: A revised or withdrawn handle is unknown or not editable. No writes from the attempt are kept.
    """
    deps = ctx.deps
    group_id = deps.mem_access_context.memory_group_id
    unknown: list[str] = []
    locked: list[str] = []

    def convention_id(handle: str) -> UUID | None:
        try:
            return deps.convention_handles.get_uuid(handle)
        except KeyError:
            unknown.append(handle)
            return None

    savepoint = deps.db.begin_nested()
    try:
        for draft in output.create:
            create_convention(
                deps.db,
                group_id,
                category=ConventionCategory.NAMING,
                title=draft.title,
                rule=draft.rule,
                rationale=draft.rationale,
                creator_type=Creator.AGENT,
            )
        for revision in output.revise:
            target = convention_id(revision.handle)
            if target is None:
                continue
            try:
                update_convention(
                    deps.db,
                    group_id,
                    target,
                    title=revision.title,
                    rule=revision.rule,
                    rationale=revision.rationale,
                    only_creator=Creator.AGENT,
                    only_pending=True,
                )
            except ConventionNotFoundException:
                locked.append(revision.handle)
        for handle in output.withdraw:
            target = convention_id(handle)
            if target is None:
                continue
            try:
                delete_convention(deps.db, group_id, target, only_creator=Creator.AGENT, only_pending=True)
            except ConventionNotFoundException:
                locked.append(handle)
    except Exception:
        savepoint.rollback()
        raise
    if not unknown and not locked:
        savepoint.commit()
        return output

    savepoint.rollback()
    problems: list[str] = []
    if unknown:
        problems.append(f"Unknown convention handles: {', '.join(unknown)}. Use handles from the context.")
    if locked:
        problems.append(
            f"Conventions {', '.join(locked)} are approved, rejected, or user-written and cannot be changed. "
            "Propose a new convention instead if one is needed."
        )
    raise ModelRetry(" ".join(problems) + " Nothing from this attempt was saved; send the full corrected output.")
