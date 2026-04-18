# NovelTL

## Quick Start

### Prerequisites

- **Docker** and **Docker Compose** (v2.0+)
- **Git**

**OR**

- **VS Code** with [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
- **Docker** (for running the dev container)
- **Git**

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/NovelTL_Dev.git
   cd NovelTL_Dev
   ```

2. **Start all services**
   ```bash
   docker compose up -d
   ```
   
   This starts:
   - **Backend** (FastAPI) on http://localhost:8000
   - **Frontend** (React + Vite) on http://localhost:5173
   - **PostgreSQL** database on port 5432
   - **Redis** queue on port 6379
   - **Worker** (ARQ) for background NER processing

3. **Apply database migrations**
   ```bash
   docker compose exec backend alembic upgrade head
   ```

4. **Seed initial data**
   ```bash
   # Create admin user (interactive - will prompt for username/password)
   docker compose exec -it backend python scripts/seed_admin.py
   
   # Create language codes
   docker compose exec backend python scripts/seed_languages.py
   ```

5. **Access the application**
   - **API Documentation**: http://localhost:8000/docs (Swagger UI)
   - **API Alternative Docs**: http://localhost:8000/redoc
   - **Frontend**: http://localhost:5173 *(coming soon)*

### Alternative: Using Dev Containers

If you're using **VS Code** or **GitHub Codespaces**, the project includes a dev container configuration for a consistent development environment.

**To use:**

1. Install the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) in VS Code

2. Open the project folder in VS Code

3. When prompted, click **"Reopen in Container"** (or use Command Palette → `Dev Containers: Reopen in Container`)

4. Once the container builds, run migrations and seed data:
   ```bash
   alembic upgrade head
   python scripts/seed_admin.py
   python scripts/seed_languages.py
   ```

5. The backend will be available at http://localhost:8000

**Note:** Dev containers automatically start PostgreSQL, Redis, and the worker service. You don't need to run `docker compose up` separately.

---