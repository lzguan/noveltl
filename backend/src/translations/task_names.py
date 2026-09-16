"""Queue names for the registered action steps.

Naming each step explicitly keeps its queue identity independent of where the
callback lives, so moving or renaming a callback no longer orphans messages that
are already queued under the generated name. The values are the names
`new_func`/`new_poll` derived from the callbacks before they were named here.

Unlike the other subsystems, these are not a publisher/worker split: job
controls resolve a step's states through `actions.registry`, so the control
plane imports the action modules either way.
"""

COMBINE_CHAPTER_COMBINE = "src.translations.actions.combine_chapter.combine"

PRUNE_MEMORIES_PREPARE = "src.translations.actions.prune_memories.prepare"
PRUNE_MEMORIES_SUBMIT = "src.translations.actions.prune_memories.submit"
PRUNE_MEMORIES_POLL = "src.translations.actions.prune_memories.poll"
PRUNE_MEMORIES_FINALIZE = "src.translations.actions.prune_memories.finalize"

TRANSLATE_PREPARE = "src.translations.actions.translate.prepare"
TRANSLATE_SUBMIT = "src.translations.actions.translate.submit"
TRANSLATE_POLL = "src.translations.actions.translate.poll"
TRANSLATE_FINALIZE = "src.translations.actions.translate.finalize"
