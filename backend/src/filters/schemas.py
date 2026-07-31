from typing import Annotated

from pydantic import Field, TypeAdapter

from src.filters.runners.python.types import PythonRunnerInput

type RunnerInput = Annotated[PythonRunnerInput, Field(discriminator="runtime_name")]
runner_input_adapter = TypeAdapter(RunnerInput)
