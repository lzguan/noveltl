"""Import action modules to register their tasks, then populate the shared registry."""

from src.translations.actions.registry import ACTION_CALLBACKS
from src.translations.actions.translate import callbacks as translate_callbacks

ACTION_CALLBACKS.update({"translate": translate_callbacks})
