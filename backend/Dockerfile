FROM python:3.12-slim AS base
WORKDIR /app
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_CACHE_DIR='/tmp/poetry_cache'
RUN apt-get update && apt-get install -y \
    git \
    openssh-client \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*
RUN pip install poetry==1.8.2
COPY pyproject.toml poetry.lock* ./

FROM base AS backend
RUN poetry install --only main,backend --no-root && rm -rf $POETRY_CACHE_DIR
COPY . .
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0"]

FROM base AS worker-pkg
RUN poetry install --only main,worker --no-root && rm -rf $POETRY_CACHE_DIR

FROM worker-pkg AS worker
COPY . .
CMD ["arq", "src.autolabels.worker.worker.WorkerSettings"]

FROM worker-pkg AS dev
RUN poetry install --with backend,worker,dev --no-root && rm -rf $POETRY_CACHE_DIRCMD ["sleep", "infinity"]