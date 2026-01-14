from typing import Annotated

from arq import ArqRedis
from fastapi import Depends

from ..redis import get_redis
from .utils import ArqDispatcher, AutoLabelDispatcher


def get_arq_dispatcher(redis : Annotated[ArqRedis, Depends(get_redis)]) -> AutoLabelDispatcher:
    return ArqDispatcher(redis)
