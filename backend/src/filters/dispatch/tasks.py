from uuid import UUID

from src.database import SessionLocal
from src.filters.celery_app import app
from src.filters.compilers.python import PythonCompiler
from src.filters.runners.python.filter_runner import PythonFilterInput, PythonFilterRunner
from src.filters.runners.python.group_runner import PythonGroupInput, PythonGroupRunner
from src.filters.runners.python.label_source_runner import PythonLabelSourceInput, PythonLabelSourceRunner
from src.filters.runners.python.map_runner import PythonMapInput, PythonMapRunner
from src.filters.schemas import RunnerInput

pycompiler = PythonCompiler()

runners = {
    "python": {
        "ls": PythonLabelSourceRunner(SessionLocal),
        "group": PythonGroupRunner(SessionLocal, compiler=pycompiler),
        "map": PythonMapRunner(SessionLocal, compiler=pycompiler),
        "filter": PythonFilterRunner(SessionLocal, compiler=pycompiler),
    }
}


@app.task(soft_time_limit=600, time_limit=660)
def run_runner_task(job_id: UUID, input: RunnerInput):
    if isinstance(input, PythonLabelSourceInput):
        runners["python"]["ls"].execute(job_id, input)
    elif isinstance(input, PythonGroupInput):
        runners["python"]["group"].execute(job_id, input)
    elif isinstance(input, PythonMapInput):
        runners["python"]["map"].execute(job_id, input)
    elif isinstance(input, PythonFilterInput):
        runners["python"]["filter"].execute(job_id, input)
