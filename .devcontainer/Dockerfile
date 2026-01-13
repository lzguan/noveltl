FROM python:3.12-slim
WORKDIR /project
ADD https://astral.sh/uv/install.sh /install.sh
RUN apt-get -y update; apt-get -y install curl

RUN chmod -R 655 /install.sh && /install.sh && rm /install.sh
ENV PATH="/root/.local/bin:$PATH"
ENV UV_PROJECT_ENVIRONMENT="/app"
COPY backend/pyproject.toml backend/uv.lock* ./
RUN uv sync --frozen --all-groups