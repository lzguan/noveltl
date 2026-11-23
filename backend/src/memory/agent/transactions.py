from collections.abc import AsyncGenerator, Awaitable, Callable, Coroutine
from contextlib import asynccontextmanager
from functools import wraps
from inspect import signature
from typing import Any

from src.memory.agent.dependencies import MemAgentDeps


@asynccontextmanager
async def workspace_transaction(deps: MemAgentDeps) -> AsyncGenerator[None]:
    if deps.mem_access_context.workspace_id is None:
        yield
        return
    try:
        yield
        await deps.db.commit()
    except BaseException:
        await deps.db.rollback()
        raise


def tool_transaction[**P, R](function: Callable[P, Awaitable[R]]) -> Callable[P, Coroutine[Any, Any, R]]:
    parameters = signature(function)

    @wraps(function)
    async def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        ctx = parameters.bind(*args, **kwargs).arguments["ctx"]
        async with workspace_transaction(ctx.deps):
            return await function(*args, **kwargs)

    return wrapped
