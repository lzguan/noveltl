# Project Structure

**Last updated:** 2026-05-10

This project is separated into a frontend and a backend. The backend is stateless and takes all data from either a Postgres database or a Redis cache. The backend can employ workers by sending tasks to the Redis cache, where the workers will pick up. Currently this project uses Arq to perform task queueing. This may change in the future.

**mermaid diagram here**

## Tools/technologies

The backend consists of a FastAPI server instance that connects to a Postgres database using Sqlachemy and uses Pydantic for data validation. The backend also has a worker instance that performs named entity recognition using a pretrained BERT model ([found here](https://huggingface.co/uer/roberta-base-finetuned-cluener2020-chinese)). Since this model is from 2020, we plan to find a newer model, train our own, or explore LLM based solutions sometime in the future. This worker instance, along with the FastAPI server, connect to a Redis instance meant to serve as a task queue using [arq](https://github.com/python-arq/arq). We plan to replace this with a more frequently updated library. 

We use [uv](https://docs.astral.sh/uv/) as package manager, [Pyrefly](https://pyrefly.org/) for type checking, and [Ruff](https://docs.astral.sh/ruff/) for linting. We prefer stricter type checking so Pyright with strict type checking would be ideal, but Pyright is much slower than Pyrefly especially on slower hardware.

The frontend is written in Typescript and uses React and ShadCN for the component library. We use pnpm for our package manager.

The frontend and backend are synchronized using FastAPI's OpenAPI generation capabilities and [Hey API](https://heyapi.dev/openapi-ts/get-started) to convert OpenAPI schema to typescript.

We use pytest for backend testing and Vitest for frontend testing. We plan to use Playwright for integration testing.

## Backend structure

Broadly speaking, the backend is divided into services, where each service handles a specific class of problems. The current existing services are as follows:

- Auth: self-explanatory. For now the project mostly just implements security described in the [fastapi docs](https://fastapi.tiangolo.com/tutorial/security/).
- Autolabels: Automatically labeling text. More details in [autolabel docs](autolabels.md)
- Filters: Search specific patterns in a certain novel/bulk operations. More details in [filters docs](filters.md)
- Editing: Serve initial data required for user editing. Details for what this does can be found in the [editor docs](editor/)
- Labels: Store and serve label data for chapters. Core functionality. Details can be found in [labeling docs](labels.md)
- Novels: Store and serve novels/chapters. Details can be found in [novels docs](novels.md)
- Languages: Store and serve supported languages. Very small service so no docs, refer to [source code](../backend/src/languages/) instead.
- Requests: Specialized service for caching "real-time" operations when editing chapters. Refer to [editor docs](editor/) for details.

The source code for the backend is in [`backend/src`](../backend/src/). Related configuration is in [`backend/pyproject.toml`](../backend/pyproject.toml).

Any given service is found in `backend/src/service_name/`. A service typically consists of some subset of the following:
- `router.py`: APIRouter object with routes attached
- `service.py`: Business logic
- `models.py`: SQLAlchemy models
- `schemas.py`: Pydantic schemas
- `permissions.py`: Permissions handling
- `exceptions.py`: Custom exceptions
- `dependencies.py`: FastAPI dependencies

The exact files a certain service contains varies. At the top level, the backend contains the following files:
- [`main.py`](../backend/src/main.py): Entry point. Includes all routers into one app object. To run, start the [backend](../compose.yaml#L78) service or run one of the following commands from [`backend/`](../backend/):
    - `uv run --no-sync uvicorn src.main:app` (for more command line options see [here](https://uvicorn.dev/#command-line-options))
    - `uv run python -m src.main --no-sync` (starts the backend with the configured parameters)
    - Note that the backend requires a working connection to a redis instance or else it will crash on startup. The backend is currently configured to run within the compose network. You can change the configuration in the `.env` file. 
- [`database.py`](../backend/src/database.py): Database connection.
- [`models.py`](../backend/src/models.py): Base SQLAlchemy models.
- [`redis_conn.py`](../backend/src/redis_conn.py): Redis connection.
- [`schemas.py`](../backend/src/schemas.py) Base Pydantic models.

## Frontend structure

The frontend is divided into a view side and an edit side. These can be found respectively in [frontend/src/view](../frontend/src/view/) and [frontend/src/edit](../frontend/src/edit/). The view side of the application should be purely for displaying novels for reading and should hence be kept as static as possible. Meanwhile, the edit side should be as dynamic as possible to reduce latency from user actions. Routes to different pages are centralized in [frontend/src/routes.ts](../frontend/src/routes.ts).

The view side of the application is relatively straightforward and can be understood simply by reading the source code. The edit side consists of a navigation page primarily to switch between novels, as well as a [novel editor](../frontend/src/edit/pages/EditNovelPage.tsx). It uses a controller found in [frontend/src/edit/pages/controller](../frontend/src/edit/pages/controller/) to synchronize the backend and frontend state using (some homemade version of) [operational transformations](https://en.wikipedia.org/wiki/Operational_transformation) as well as a custom-made rendering library found in [frontend/src/components/labeled-text-lib/](../frontend/src/components/labeled-text-lib/). Real time collaboration is not supported (yet). All corresponding documentation can be found in the [editor docs](editor/).
