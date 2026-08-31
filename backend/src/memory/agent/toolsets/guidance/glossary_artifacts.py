from src.memory.agent.toolsets.guidance import create_guidance_toolset

GLOSSARY_ARTIFACT_INSTRUCTIONS = """
Create `item` terms selectively for named unique objects or recurring classes
of fantastical objects whose identity or rendering matters later. Define an
eligible item's stable intrinsic function, nature, and important operating
constraint. Do not turn its discovery scene, current owner, or complete history
into its definition.

When the relevant toolsets are enabled, use an `ownership` relation for a
durable owner and an event for a consequential acquisition, loss, destruction,
sealing, repair, or irreversible transformation. Do not record generic
equipment, ordinary consumables, short-lived loot, prices, inventory churn,
every use in combat, or an upgrade that does not materially change later
understanding of the object.
""".strip()

glossary_artifact_toolset = create_guidance_toolset("glossary_artifacts", GLOSSARY_ARTIFACT_INSTRUCTIONS)
