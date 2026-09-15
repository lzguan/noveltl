"""Import action modules to register their tasks, then populate the shared registry."""

from src.translations.actions.combine_chapter import callbacks as combine_chapter_callbacks
from src.translations.actions.registry import ACTION_CALLBACKS
from src.translations.actions.translate import callbacks as translate_callbacks

ACTION_CALLBACKS.update({"translate": translate_callbacks, "combine_chapter": combine_chapter_callbacks})
