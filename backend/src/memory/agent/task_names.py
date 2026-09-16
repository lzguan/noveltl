"""Queue names shared by the API publisher and the worker registration.

Importable without the agent dependency group, so API processes can publish work
without importing the task implementations. The values are the names Celery
generated from the task functions before they were named explicitly, so
already-queued messages stay deliverable. Keep them in step with any move of
the defining module rather than letting Celery regenerate them.
"""

RUN_MEMORY_JOB = "src.memory.agent.dispatch.celery.run_memory_job"
RUN_MEMORY_TASK = "src.memory.agent.dispatch.celery.run_memory_task"
