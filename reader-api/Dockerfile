FROM ghcr.io/astral-sh/uv:0.13.6-python3.15-trixie-slim AS base

ARG GNAME=newgroup
ARG UNAME=newuser
ARG UID=1000
ARG GID=1000

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

RUN groupadd -r -g ${GID} ${GNAME} && useradd -u ${UID} -ms /bin/bash ${UNAME} -g ${GNAME}
USER ${UNAME}
WORKDIR /home/${UNAME}/reader-api
COPY --chown=${UNAME}:${GNAME} pyproject.toml uv.lock* ./

RUN --mount=type=cache,target=/home/${UNAME}/.cache/uv,uid=${UID},gid=${GID} uv sync --locked --no-default-groups --no-install-project

FROM base AS reader-api
COPY --chown=${UNAME}:${GNAME} . .

EXPOSE 8001

CMD ["uv", "run", "--no-sync", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]
