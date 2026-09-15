from src.translations.actions.actions import ActionCallbacks, ActionStep
from src.translations.types import ActionName, TranslationTaskStatus

ACTION_CALLBACKS: dict[ActionName, ActionCallbacks] = {}


def last_step(action: ActionName, state: TranslationTaskStatus) -> ActionStep | None:
    """Resolve the resumable step from the action's registered lifecycle."""
    return ACTION_CALLBACKS[action].last_step(state)
