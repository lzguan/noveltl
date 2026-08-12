from typing import Literal

from src.filters.runners.interfaces.runner import Runner, RunnerInputBase


class PythonRunnerInputBase(RunnerInputBase):
    runtime_name: Literal["python"]


class PythonRunner[RunnerInputT: PythonRunnerInputBase](Runner[RunnerInputT]):
    pass
