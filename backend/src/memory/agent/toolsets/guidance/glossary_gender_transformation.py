from src.memory.agent.toolsets.guidance import create_guidance_toolset

GLOSSARY_GENDER_TRANSFORMATION_INSTRUCTIONS = """
Handle gender-related continuity by distinguishing an actual persistent change
from a reveal, disguise, temporary transformation, possession, body swap, or
avatar. A persistent change to the person's current state supersedes the
corresponding `gender` fact. When the event toolset is enabled, the
transformation itself may also be recorded as a consequential event.

A disguise or temporary form does not supersede canonical gender. A reveal
corrects previously concealed or mistaken context rather than inventing an
in-world transformation. Do not treat a body's traits as the occupant's gender
identity unless the text does. Give a separately recurring avatar, body, or
persona its own `person` term when the story treats it as an independently
referenced identity; connect equivalent identities with an `alias` relation
when the relation toolset is enabled.
""".strip()

glossary_gender_transformation_toolset = create_guidance_toolset(
    "glossary_gender_transformation",
    GLOSSARY_GENDER_TRANSFORMATION_INSTRUCTIONS,
)
