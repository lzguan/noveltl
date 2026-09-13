"""Callback contracts; action implementations and worker wiring live elsewhere."""

import uuid
from collections.abc import Callable
from typing import Protocol

type ActionCallback = Callable[[uuid.UUID], None]  # task id


class ActionCallbacks(Protocol):
    """
    Conceptually, entrypoint should be a function that dispatches a task to the "next" step in this action, and exitpoint should be a function that dispatches the entrypoint to the "next" action in the stages pipeline. new_func should take a plain function and record it as a dispatcher for a step in this action, which then automatically dispatches the next step at the end.

    In practice the implementation will be absolutely cursed. This doesn't matter because this is a personal project, but I would not recommend using this as a model for your own code. Admittedly this implementation is kind of an experiment.
    """

    def entrypoint(self, x: uuid.UUID) -> None: ...

    def exitpoint(self, x: uuid.UUID) -> None: ...

    def new_func(self, f: ActionCallback) -> ActionCallback: ...
