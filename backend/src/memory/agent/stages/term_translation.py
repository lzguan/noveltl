from pydantic_ai import AgentRunResult

from src.memory.agent.agents.term_translation import create_term_translation_agent
from src.memory.agent.capabilities.term_translation import TermTranslationOutput
from src.memory.agent.config import TranslateTermsStageConfig
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.prompts.term_translation import term_translation_request_prompt
from src.memory.agent.toolsets.translations.tools import term_translation_context


async def run_term_translation_stage(
    deps: MemAgentDeps,
    chapter_text: str,
    chapter_num: int,
    language_name: str,
    config: TranslateTermsStageConfig,
) -> AgentRunResult[TermTranslationOutput] | None:
    glossary_context = term_translation_context(
        deps.db, deps.mem_access_context, include_conventions=config.include_conventions
    )
    if deps.mem_access_context.workspace_id is not None:
        deps.db.commit()
    if glossary_context is None:
        return None
    agent = create_term_translation_agent(
        config.model_name, tuple(term.term for term in glossary_context.requested_terms), config.include_conventions
    )
    async with agent:
        return await agent.run(
            term_translation_request_prompt(chapter_text, chapter_num, language_name, glossary_context),
            deps=deps,
        )
