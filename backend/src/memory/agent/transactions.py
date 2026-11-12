from collections.abc import Awaitable, Callable, Coroutine, Generator
from contextlib import contextmanager
from functools import wraps
from inspect import signature
from typing import Any, Concatenate

from pydantic_ai import RunContext

from src.memory.agent.dependencies import MemAgentDeps


@contextmanager
def workspace_transaction(deps: MemAgentDeps) -> Generator[None]:
    if deps.mem_access_context.workspace_id is None:
        yield
        return
    try:
        yield
        deps.db.commit()
    except BaseException:
        deps.db.rollback()
        raise


def tool_transaction[**P, R](
    function: Callable[Concatenate[RunContext[MemAgentDeps], P], R],
) -> Callable[Concatenate[RunContext[MemAgentDeps], P], R]:
    @wraps(function)
    def wrapped(ctx: RunContext[MemAgentDeps], /, *args: P.args, **kwargs: P.kwargs) -> R:
        with workspace_transaction(ctx.deps):
            return function(ctx, *args, **kwargs)

    return wrapped


def atool_transaction[**P, R](function: Callable[P, Awaitable[R]]) -> Callable[P, Coroutine[Any, Any, R]]:
    parameters = signature(function)

    @wraps(function)
    async def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        ctx = parameters.bind(*args, **kwargs).arguments["ctx"]
        with workspace_transaction(ctx.deps):
            return await function(*args, **kwargs)

    return wrapped
