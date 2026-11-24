FROM ghcr.io/astral-sh/uv:0.13.6-python3.15-trixie-slim AS base

ARG GNAME=newgroup
ARG UNAME=newuser
ARG UID=1000
ARG GID=1000

ENV LOG_LEVEL=INFO
ENV LOG_OUTPUT=STREAM
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

RUN groupadd -r -g ${GID} ${GNAME} && useradd -u ${UID} -ms /bin/bash ${UNAME} -g ${GNAME}
USER ${UNAME}
WORKDIR /home/${UNAME}/backend
COPY --chown=${UNAME}:${GNAME} pyproject.toml uv.lock* ./

RUN --mount=type=cache,target=/home/${UNAME}/.cache/uv,uid=${UID},gid=${GID} uv sync --locked --no-default-groups --no-install-project

FROM base AS backend
RUN --mount=type=cache,target=/home/${UNAME}/.cache/uv,uid=${UID},gid=${GID} uv sync --locked --no-default-groups --group backend --group celery --group taskiq --no-install-project
COPY --chown=${UNAME}:${GNAME} . .

CMD ["uv", "run", "--no-sync", "uvicorn", "src.main:app", "--host", "0.0.0.0"]

FROM base AS autolabels-worker
RUN --mount=type=cache,target=/home/${UNAME}/.cache/uv,uid=${UID},gid=${GID} uv sync --locked --no-default-groups --group worker --group celery --no-install-project
COPY --chown=${UNAME}:${GNAME} . .

ARG CLUENER_REVISION=cddd8fc233e373855a8c0a7f4b7eb83acb686a2b
RUN uv run --no-sync hf download \
      uer/roberta-base-finetuned-cluener2020-chinese \
      config.json \
      pytorch_model.bin \
      special_tokens_map.json \
      tokenizer_config.json \
      vocab.txt \
      --revision ${CLUENER_REVISION}
CMD ["uv", "run", "--no-sync", "celery", "-A", "src.autolabels.inference.celery_app", "worker", "--loglevel=info"]

FROM base AS filters-worker
# Nothing reachable from src.filters.celery_app imports FastAPI or torch, so only Celery is added.
RUN --mount=type=cache,target=/home/${UNAME}/.cache/uv,uid=${UID},gid=${GID} uv sync --locked --no-default-groups --group celery --no-install-project
COPY --chown=${UNAME}:${GNAME} . .

CMD ["uv", "run", "--no-sync", "celery", "-A", "src.filters.celery_app", "worker", "--loglevel=info"]

FROM base AS jobs-worker
# Generic database-bound jobs (see src/jobs). Task modules import only base dependencies and taskiq.
RUN --mount=type=cache,target=/home/${UNAME}/.cache/uv,uid=${UID},gid=${GID} uv sync --locked --no-default-groups --group taskiq --no-install-project
COPY --chown=${UNAME}:${GNAME} . .

CMD ["uv", "run", "--no-sync", "taskiq", "worker", "src.jobs.broker:broker", "src.autolabels.promotions.tasks"]

FROM base AS memory-agent-worker
RUN --mount=type=cache,target=/home/${UNAME}/.cache/uv,uid=${UID},gid=${GID} uv sync --locked --no-default-groups --group agent --group taskiq --no-install-project
COPY --chown=${UNAME}:${GNAME} . .

# One process: agent tasks are mostly waiting on the model, so one event loop runs many of them.
CMD ["uv", "run", "--no-sync", "taskiq", "worker", "src.memory.agent.broker:broker", "src.memory.agent.dispatch.taskiq_worker", "--workers", "1", "--max-async-tasks", "64"]

FROM base AS translations-worker
RUN --mount=type=cache,target=/home/${UNAME}/.cache/uv,uid=${UID},gid=${GID} uv sync --locked --no-default-groups --group tagent --group taskiq --no-install-project
COPY --chown=${UNAME}:${GNAME} . .

# One process: steps mostly wait on providers. Each step may hold two database connections
# (its transaction and a lease renewal), so the pool in taskiq_actions.py is sized to 2x this.
CMD ["uv", "run", "--no-sync", "taskiq", "worker", "src.translations.broker:broker", "src.translations.actions", "--workers", "1", "--max-async-tasks", "16"]
