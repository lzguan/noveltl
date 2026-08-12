from uuid import UUID

from src.database import SessionLocal
from src.filters.compilers.python import PythonCompiler
from src.filters.runners.python.annotation_runner import PythonAnnotationInput, PythonAnnotationRunner
from src.filters.runners.python.filter_runner import PythonFilterInput, PythonFilterRunner
from src.filters.runners.python.group_runner import PythonGroupInput, PythonGroupRunner
from src.filters.runners.python.label_source_runner import PythonLabelSourceInput, PythonLabelSourceRunner
from src.filters.runners.python.map_runner import PythonMapInput, PythonMapRunner
from src.filters.schemas import RunnerInput

pycompiler = PythonCompiler()

runners = {
    "python": {
        "annotation": PythonAnnotationRunner(SessionLocal),
        "ls": PythonLabelSourceRunner(SessionLocal),
        "group": PythonGroupRunner(SessionLocal, compiler=pycompiler),
        "map": PythonMapRunner(SessionLocal, compiler=pycompiler),
        "filter": PythonFilterRunner(SessionLocal, compiler=pycompiler),
    }
}


def run_runner(job_id: UUID, input: RunnerInput) -> None:
    if isinstance(input, PythonAnnotationInput):
        runners["python"]["annotation"].execute(job_id, input)
    elif isinstance(input, PythonLabelSourceInput):
        runners["python"]["ls"].execute(job_id, input)
    elif isinstance(input, PythonGroupInput):
        runners["python"]["group"].execute(job_id, input)
    elif isinstance(input, PythonMapInput):
        runners["python"]["map"].execute(job_id, input)
    elif isinstance(input, PythonFilterInput):
        runners["python"]["filter"].execute(job_id, input)
