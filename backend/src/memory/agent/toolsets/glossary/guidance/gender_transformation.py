from src.memory.agent.toolsets.glossary.guidance import create_guidance_toolset

GLOSSARY_GENDER_TRANSFORMATION_INSTRUCTIONS = """
Handle gender-related continuity by distinguishing an actual persistent change
from a reveal, disguise, temporary transformation, possession, body swap, or
avatar. A persistent change to the person's current state supersedes the
corresponding `body` or `identity` memory. When
`new_gender_event_memory` is available, the transformation itself may also be
recorded as a consequential event.

A disguise or temporary form does not supersede canonical gender. A reveal
corrects previously concealed or mistaken context rather than inventing an
in-world transformation. Do not treat a body's traits as the occupant's gender
identity unless the text does. Give a separately recurring avatar, body, or
persona its own `person` term when the story treats it as an independently
referenced identity; when `new_relation_memory` is available, connect
equivalent identities with an `alias` relation. When a persistent gender change also
introduces a new recurring name, retrieve the old name's gender memory and
supersede it using the new exact name as the replacement `term_name`. The old
memory should end under the old name, the replacement should be active under the
new name, and the alias relation should preserve their identity continuity.

Do not collapse body state and self-identity into one memory. Do not include
attraction, reactions, adaptation, pronoun evidence, or transformation history
inside either current-state fact. Gender-related events and current gender
facts are separate records and should not repeat the same prose.
""".strip()

glossary_gender_transformation_toolset = create_guidance_toolset(
    "glossary_gender_transformation",
    GLOSSARY_GENDER_TRANSFORMATION_INSTRUCTIONS,
)
