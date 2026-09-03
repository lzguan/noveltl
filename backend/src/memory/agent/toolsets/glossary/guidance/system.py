from src.memory.agent.toolsets.glossary.guidance import create_guidance_toolset

GLOSSARY_SYSTEM_INSTRUCTIONS = """
Treat a story's system, interface, status panel, quests, and rewards as distinct
kinds of information. Preserve stable system mechanics and permanent unlocks
that will matter to later interpretation. For a recurring person, record only
current ranks, classes, permanent traits, lasting abilities, or limitations
whose omission could cause a continuity error.

Do not copy whole status panels or record routine notifications, transient
statistics, temporary buffs, unaccepted quests, hypothetical rewards,
countdowns, ordinary inventory changes, or every numeric increase. A displayed
value is not automatically important. Supersede the same tracked attribute
when a permanent new value replaces it; keep independent attributes separate.
Use definitions for the stable meaning of named system concepts when that
toolset is enabled.
""".strip()

glossary_system_toolset = create_guidance_toolset("glossary_system", GLOSSARY_SYSTEM_INSTRUCTIONS)
