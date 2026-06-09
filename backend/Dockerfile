FROM python:3.12-slim AS base

ARG GNAME=newuser
ARG UNAME=newuser
ARG UID=1001
ARG GID=1001

ENV LOG_LEVEL=INFO
ENV LOG_OUTPUT=STREAM

RUN groupadd -r -g ${GID} ${GNAME} && useradd -u ${UID} -ms /bin/bash ${UNAME} -g ${GNAME}

RUN mkdir -p /home/${UNAME}/.cache/uv && chown -R ${UNAME}:${GNAME} /home/${UNAME}/.cache/uv 
RUN mkdir -p /home/${UNAME}/backend && chown -R ${UNAME}:${GNAME} /home/${UNAME}/backend
RUN mkdir -p /home/${UNAME}/backend/.venv && chown -R ${UNAME}:${GNAME} /home/${UNAME}/backend/.venv
RUN mkdir -p /home/${UNAME}/.cache/huggingface && chown -R ${UNAME}:${GNAME} /home/${UNAME}/.cache/huggingface

WORKDIR /home/${UNAME}/backend
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY pyproject.toml uv.lock* ./

USER ${UNAME}
RUN --mount=type=cache,target=/home/${UNAME}/.cache/uv,uid=${UID},gid=${GID} uv sync --frozen --no-default-groups --no-install-project

FROM base AS backend
RUN --mount=type=cache,target=/home/${UNAME}/.cache/uv,uid=${UID},gid=${GID} uv sync --frozen --group backend --no-group worker --no-group dev --no-install-project
COPY . .
CMD ["uv", "run", "--no-sync", "uvicorn", "src.main:app", "--host", "0.0.0.0"]

FROM base AS worker
RUN --mount=type=cache,target=/home/${UNAME}/.cache/uv,uid=${UID},gid=${GID} uv sync --frozen --group worker --no-group backend --no-group dev --no-install-project
RUN --mount=type=cache,target=/tmp/hf_dl,uid=${UID},gid=${GID} uv run --no-sync hf download uer/roberta-base-finetuned-cluener2020-chinese --cache-dir /tmp/hf_dl && cp -r /tmp/hf_dl /home/${UNAME}/.cache/huggingface
COPY . .
CMD ["uv", "run", "--no-sync", "arq", "src.autolabels.worker.worker.WorkerSettings"]
