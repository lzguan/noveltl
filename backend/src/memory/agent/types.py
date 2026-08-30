from typing import Literal

type ModelName = Literal["deepseek:deepseek-v4-flash-none", "deepseek:deepseek-v4-flash-low"]
type ToolsetName = Literal[
    "glossary_terms",
    "glossary_definitions",
    "glossary_relations",
    "glossary_facts",
    "glossary_events",
]
