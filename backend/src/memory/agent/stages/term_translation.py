from pydantic_ai import AgentRunResult

from src.memory.agent.agent import create_term_translation_agent
from src.memory.agent.capabilities.term_translation import TermTranslationOutput
from src.memory.agent.config import TranslateTermsStageConfig
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.prompts.term_translation import term_translation_request_prompt
from src.memory.agent.toolsets.translations.tools import TermTranslationContext


async def run_term_translation_stage(
    deps: MemAgentDeps,
    chapter_text: str,
    chapter_num: int,
    language_name: str,
    config: TranslateTermsStageConfig,
    glossary_context: TermTranslationContext,
) -> AgentRunResult[TermTranslationOutput]:
    agent = create_term_translation_agent(
        config.model_name, tuple(term.term for term in glossary_context.requested_terms)
    )
    async with agent:
        return await agent.run(
            term_translation_request_prompt(chapter_text, chapter_num, language_name, glossary_context),
            deps=deps,
        )
