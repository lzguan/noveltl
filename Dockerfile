FROM python:3.12-slim

# 1. Install System Dependencies
# libpq-dev and gcc are often needed for building python db drivers
RUN apt-get update && apt-get install -y \
    git \
    openssh-client \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 2. Configure Poetry
# Virtualenvs are bad in Docker (Inception). We turn them off.
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_CACHE_DIR='/tmp/poetry_cache'

# 3. Install Poetry (System-wide)
RUN pip install poetry==1.8.2

WORKDIR /app

# 4. Install Dependencies
# We copy ONLY the dependency files first to cache this layer
COPY pyproject.toml poetry.lock* ./

# Install dependencies (Main + Dev) as ROOT
RUN poetry install --no-root && rm -rf $POETRY_CACHE_DIR

# 5. User Setup
# Create user
RUN adduser -u 5678 --disabled-password --gecos "" appuser && chown -R appuser /app

# 6. Copy Code
COPY . .

# 7. Switch User (Everything is already installed in global path!)
USER appuser

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]