"""Queue names shared by the API publisher and the worker registration.

Importable without the runner implementation, so API processes can publish work
without importing it. The values are the names Celery generated from the task
functions before they were named explicitly, so already-queued messages stay
deliverable. Keep them in step with any move of the defining module rather than
letting Celery regenerate them.
"""

RUN_RUNNER_TASK = "src.filters.dispatch.celery.run_runner_task"
