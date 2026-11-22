from sqlalchemy import SQLColumnExpression, case, literal

from src.translations.actions.actions import ActionCallbacks, ActionStep
from src.translations.types import ActionName, TranslationTaskStatus

ACTION_CALLBACKS: dict[ActionName, ActionCallbacks] = {}


def resume_step(action: ActionName, state: TranslationTaskStatus) -> ActionStep | None:
    """Resolve the resumable step from the action's registered lifecycle."""
    return ACTION_CALLBACKS[action].resume_step(state)


def resume_step_sql(action: SQLColumnExpression[str], state: SQLColumnExpression[str]):
    """SQL restart states generated from the same registrations as dispatch."""
    mapping: dict[str, str] = {}
    for name, callbacks in ACTION_CALLBACKS.items():
        for status in TranslationTaskStatus:
            try:
                step = callbacks.resume_step(status)
            except ValueError:
                continue
            if step is not None:
                mapping[f"{name}:{status}"] = str(step.expect)
    return case(mapping, value=action + literal(":") + state)
