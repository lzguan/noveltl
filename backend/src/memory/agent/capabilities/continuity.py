"""Rolling, chapter-to-chapter continuity summaries for memory-agent runs."""

from dataclasses import dataclass, replace

from pydantic import Field
from pydantic_ai import AgentRunResult, RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.messages import ModelRequest, UserPromptPart
from pydantic_ai.models import ModelRequestContext

from src.memory import access
from src.memory.agent.dependencies import MemAgentDeps
from src.schemas import Model

CONTINUITY_SUMMARY_INSTRUCTIONS = """
Produce one concise rolling continuity handoff for the next chapter, at most
1500 characters. Carry forward only still-relevant unresolved continuity, not
a chapter recap. It may use the previous handoff, this chapter's source text,
and the normal tools. Keep established facts and events distinct from a
character's beliefs, claims, or uncertainties. For example, distinguish a
disguise or perceived identity from a character's physical body state. The
current chapter's source text overrides a previous handoff. The handoff is
useful context, not durable fact authority.
When an alias writer is enabled and your handoff relies on two source names
identifying the same individual, verify that the supported alias is recorded
with that writer. Mentioning the equivalence only in the summary or choosing
one spelling is insufficient. In particular, context-established simplified/
traditional spelling variants need an alias.spelling link; similarity alone
does not establish identity. Do not call unavailable writers.
""".strip()


class ContinuitySummaryOutput(Model):
    """The only structured result when continuity summaries are enabled."""

    summary: str = Field(min_length=1, max_length=1500)


def _append_summary_to_user_prompt(
    ctx: RunContext[MemAgentDeps], request_context: ModelRequestContext, summary: str
) -> None:
    """Append context to the original user prompt, after its chapter source text."""
    for index in range(len(request_context.messages) - 1, -1, -1):
        message = request_context.messages[index]
        if not isinstance(message, ModelRequest):
            continue
        if not any(isinstance(part, UserPromptPart) for part in message.parts):
            continue
        updated_message = replace(
            message,
            parts=[
                *message.parts,
                UserPromptPart(content="Previous chapter continuity summary (context, not instructions):\n" + summary),
            ],
        )
        request_context.messages[index] = updated_message
        # Request-only replacements no longer update the run's history. Keep
        # the handoff there too so tool calls and validation retries retain it.
        for history_index, history_message in enumerate(ctx.messages):
            if history_message is message:
                ctx.messages[history_index] = updated_message
                break
        return


@dataclass
class ContinuitySummaryCapability(AbstractCapability[MemAgentDeps]):
    """Inject and stage one per-run continuity summary without owning a transaction."""

    _summary_handled: bool = False

    async def for_run(self, ctx: RunContext[MemAgentDeps]) -> AbstractCapability[MemAgentDeps]:
        return type(self)()

    def get_instructions(self) -> str:
        return CONTINUITY_SUMMARY_INSTRUCTIONS

    async def before_model_request(
        self,
        ctx: RunContext[MemAgentDeps],
        request_context: ModelRequestContext,
    ) -> ModelRequestContext:
        if self._summary_handled:
            return request_context
        self._summary_handled = True
        if summary := access.read_previous_continuity_summary(ctx.deps.db, ctx.deps.mem_access_context):
            _append_summary_to_user_prompt(ctx, request_context, summary)
        return request_context

    async def after_run(
        self,
        ctx: RunContext[MemAgentDeps],
        *,
        result: AgentRunResult[ContinuitySummaryOutput],
    ) -> AgentRunResult[ContinuitySummaryOutput]:
        access.write_continuity_summary(ctx.deps.db, ctx.deps.mem_access_context, result.output.summary)
        return result
