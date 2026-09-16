"""Queue names shared by the API publisher and the worker registration.

Importable without the inference implementation, so API processes can publish
work without importing it. The values are the names Celery generated from the
task functions before they were named explicitly, so already-queued messages
stay deliverable. Keep them in step with any move of the defining module rather
than letting Celery regenerate them.
"""

CELERY_INFER = "src.autolabels.dispatch.celery.celery_infer"
