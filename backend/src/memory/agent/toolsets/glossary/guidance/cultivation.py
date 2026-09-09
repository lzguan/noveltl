from src.memory.agent.toolsets.glossary.guidance import create_guidance_toolset

GLOSSARY_CULTIVATION_INSTRUCTIONS = """
Track a recurring person's current, completed cultivation level when it is
explicitly established. Keep independent cultivation tracks separate, such as
spiritual cultivation, body refinement, soul cultivation, or a secondary
path. Name the track in the fact whenever more than one can exist, and
supersede only the previous value for that same track.

Do not record attempted or projected breakthroughs, momentary combat output,
temporary boosts, borrowed power, concealed apparent levels, or every
intermediate number shown during training as the person's canonical level. A
persistent regression, crippled foundation, restored level, or completed
breakthrough may supersede the corresponding current fact. Put stable meanings
of named realms, techniques, pills, and cultivation resources in definitions
when that toolset is enabled; do not duplicate those meanings as person facts.
""".strip()

glossary_cultivation_toolset = create_guidance_toolset(
    "glossary_cultivation",
    GLOSSARY_CULTIVATION_INSTRUCTIONS,
)
