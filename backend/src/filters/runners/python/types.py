from typing import Annotated

from pydantic import Field, TypeAdapter

from src.filters.runners.python.annotation_runner import PythonAnnotationInput
from src.filters.runners.python.filter_runner import PythonFilterInput
from src.filters.runners.python.group_runner import PythonGroupInput
from src.filters.runners.python.label_source_runner import PythonLabelSourceInput
from src.filters.runners.python.map_runner import PythonMapInput

type PythonRunnerInput = Annotated[
    PythonAnnotationInput | PythonFilterInput | PythonGroupInput | PythonLabelSourceInput | PythonMapInput,
    Field(discriminator="runner_name"),
]

python_runner_input_adapter = TypeAdapter(PythonRunnerInput)
