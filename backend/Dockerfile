FROM ghcr.io/astral-sh/uv:0.12.1-python3.12-trixie-slim AS base

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
RUN --mount=type=cache,target=/home/${UNAME}/.cache/uv,uid=${UID},gid=${GID} uv sync --locked --group backend --no-group worker --no-group dev --no-install-project
COPY --chown=${UNAME}:${GNAME} . .

CMD ["uv", "run", "--no-sync", "uvicorn", "src.main:app", "--host", "0.0.0.0"]

FROM base AS autolabels-worker
RUN --mount=type=cache,target=/home/${UNAME}/.cache/uv,uid=${UID},gid=${GID} uv sync --locked --group worker --no-group backend --no-group dev --no-group agent --no-install-project
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
CMD ["uv", "run", "--no-sync", "celery", "-A", "src.autolabels.celery_app", "worker", "--loglevel=info"]

FROM base AS filters-worker
# The filter runners need only the base dependencies. Nothing reachable from
# src.filters.celery_app imports FastAPI or torch, so no dependency group is synced here.
COPY --chown=${UNAME}:${GNAME} . .

CMD ["uv", "run", "--no-sync", "celery", "-A", "src.filters.celery_app", "worker", "--loglevel=info"]

FROM base AS memory-agent-worker
RUN --mount=type=cache,target=/home/${UNAME}/.cache/uv,uid=${UID},gid=${GID} uv sync --locked --group agent --no-group backend --no-group worker --no-group dev --no-install-project
COPY --chown=${UNAME}:${GNAME} . .

CMD ["uv", "run", "--no-sync", "celery", "-A", "src.memory.agent.celery_app", "worker", "--loglevel=info"]
