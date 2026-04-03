from typing import Annotated

from arq import ArqRedis
from fastapi import Depends

from ..redis import get_redis
from .utils import ArqTranslationDispatcher, TranslationDispatcher


def get_translation_dispatcher(redis: Annotated[ArqRedis, Depends(get_redis)]) -> TranslationDispatcher:
    return ArqTranslationDispatcher(redis)
