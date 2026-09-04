from src.memory.agent.toolsets.glossary.guidance import create_guidance_toolset

GLOSSARY_GENDER_TRANSFORMATION_INSTRUCTIONS = """
Handle gender-related continuity by distinguishing body, self-identity,
presentation as oneself, another observer's perception, a durable change rule,
and a bounded transformation, reveal, possession, or body swap. A change to
current body, identity, or presentation supersedes that same fact aspect. A
repeatable ability, involuntary trigger, or constraint belongs in a
`change_rule` fact. A consequential transformation occurrence may separately
use `new_gender_transformation_event_memory` when that tool is available.

A disguise, cover identity, or assumed persona is not presentation as oneself
and belongs to a disguise toolset when one is provided. Otherwise ignore the
disguise-specific state rather than forcing it into these gender tools. A
reveal corrects previously concealed or mistaken context rather than inventing
an in-world transformation. Do not treat a body's traits as the occupant's
identity unless the text does. Give a separately recurring avatar or body its
own `person` term when the story independently references it. If a persistent
gender change introduces a new recurring name, retrieve the old name's gender
state and supersede the appropriate aspect using the new exact `term_name`;
identity continuity between aliases remains the generic relation toolset's
responsibility when it is enabled.

Store `Observer perceives Subject as ...` through the advanced gender
perception tools only when Subject appears as themself. A mistaken perception
still belongs in that relation and never overwrites Subject's actual facts.
Keep different observers separate. An observer's belief about a disguised
identity belongs to a disguise toolset when one is provided and must otherwise
be ignored.

Do not collapse body, identity, presentation, perception, or a change rule into
one memory. Do not include attraction, reactions, adaptation, pronoun evidence,
or transformation history inside current-state facts. Gender-related events,
facts, and perceptions are separate records and should not repeat the same
prose.
""".strip()

glossary_gender_transformation_toolset = create_guidance_toolset(
    "glossary_gender_transformation",
    GLOSSARY_GENDER_TRANSFORMATION_INSTRUCTIONS,
)
