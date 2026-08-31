from src.memory.agent.toolsets.guidance import create_guidance_toolset

GLOSSARY_GENDER_INSTRUCTIONS = """
For recurring `person` terms, preserve explicitly established current gender
even when it seems mundane, because forgetting it can cause pronoun and other
translation errors. Treat unambiguous narration, self-identification, or a
direct statement as evidence. Do not infer gender from a name, clothing,
appearance, occupation, social role, or stereotype alone.

Store one short `gender` fact for the exact person when the current value is
established. Do not create repeated facts for pronouns or restatements. If the
source distinguishes gender identity, physical sex, or presentation, state the
exact attribute instead of collapsing them into one vague claim. Otherwise use
a simple current-gender statement.
""".strip()

glossary_gender_toolset = create_guidance_toolset("glossary_gender", GLOSSARY_GENDER_INSTRUCTIONS)
