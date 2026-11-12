"""Structured naming output and transaction-scoped translation writes."""

from typing import Annotated, Self

from pydantic import Field, StringConstraints, model_validator
from pydantic_ai import AgentRunResult, RunContext
from pydantic_ai.capabilities import AbstractCapability

from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.transactions import atool_transaction
from src.memory.plugins.translations.access import create_term_translation
from src.schemas import Model


class NamedTerm(Model):
    term: str = Field(min_length=1, description="Exact source-language glossary form.")
    translation: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(
        description="Canonical rendering in the requested target language."
    )


class TermTranslationOutput(Model):
    translations: list[NamedTerm]

    @model_validator(mode="after")
    def unique_source_terms(self) -> Self:
        names = [item.term for item in self.translations]
        if len(names) != len(set(names)):
            raise ValueError("Each source term must occur exactly once")
        return self


class TermTranslationCapability(AbstractCapability[MemAgentDeps]):
    @atool_transaction
    async def after_run(
        self, ctx: RunContext[MemAgentDeps], *, result: AgentRunResult[TermTranslationOutput]
    ) -> AgentRunResult[TermTranslationOutput]:
        for item in result.output.translations:
            create_term_translation(ctx.deps.db, ctx.deps.mem_access_context, item.term, item.translation)
        return result
