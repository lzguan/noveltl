from pydantic_ai import FunctionToolset, ModelRetry, RunContext
from sqlalchemy.exc import IntegrityError

from src.memory.agent.dependencies import MemAgentDeps
from src.memory.plugins.glossary import access
from src.memory.plugins.glossary.types import TermKind

GLOSSARY_TERM_INSTRUCTIONS = """
Create source-language glossary terms selectively. A term must be likely to
recur and its rendering or identity must matter to later translation. Avoid
ordinary vocabulary, disposable descriptions, and unnamed one-off roles.

Classify every term as `person`, `place`, `organization`, `technique`, `item`,
`concept`, `title`, `species`, or `other`. Use `other` only when a
translation-relevant recurring term fits none of the specific kinds. Adding a
term does not require creating a memory for it. Never add a term merely so
another enabled toolset has something to write, and never add a term already
present in the initial glossary context.
""".strip()


def add_term(ctx: RunContext[MemAgentDeps], term_name: str, term_kind: TermKind) -> str:
    """Add and classify one new exact source-language glossary term."""
    db = ctx.deps.db
    try:
        with db.begin_nested():
            new_term = access.create_term(
                db,
                ctx.deps.mem_access_context.memory_group_id,
                term_name,
                term_kind,
            )
            result = f"Term {new_term.term} added successfully."
    except IntegrityError as exc:
        diagnostic = getattr(exc.orig, "diag", None)
        if getattr(diagnostic, "constraint_name", None) == "uq_glossaries_term_memory_group_id":
            raise ModelRetry(f"Glossary term {term_name!r} already exists. Do not add it again.") from exc
        raise
    return result


glossary_term_toolset = FunctionToolset(
    tools=[add_term],
    instructions=[GLOSSARY_TERM_INSTRUCTIONS],
    sequential=True,
)
