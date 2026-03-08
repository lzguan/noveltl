# NovelTL

**Disclaimer: This document is AI generated and has not been vetted yet.**


**A collaborative platform for novel translation using Named Entity Recognition (NER) and LLM-assisted workflows.**

NovelTL helps translators efficiently identify, label, and translate named entities (characters, locations, terms) across long-form works like web novels, ensuring consistent terminology across hundreds of chapters.

---

## 🎯 Key Features

- **Automated Entity Detection** - NER models automatically identify character names, locations, and terms
- **Manual Label Management** - Review, edit, and verify AI-generated labels with full context
- **Smart Filtering** - Four-phase filter pipeline to clean up false positives at scale
- **Collaborative Workflows** - Role-based permissions for teams working on the same novel
- **Revision System** - Chapter versioning ensures labels remain valid as text evolves
- **Background Processing** - Async worker queue for computationally expensive NER tasks
- **Glossary Generation** - Aggregate labels into translation glossaries (planned)

---

## 🚀 Quick Start

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
   - **Frontend** (React + Vite) on http://localhost:3000 *(when implemented)*
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
   - **Frontend**: http://localhost:3000 *(coming soon)*

### Alternative: Using Dev Containers

If you're using **VS Code** or **GitHub Codespaces**, the project includes a dev container configuration for a consistent development environment.

**Benefits:**
- Pre-configured Python environment with all dependencies
- Integrated database, Redis, and worker services
- VS Code extensions and settings already configured
- No need to install Python, Node, or other tools locally

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

## 📁 Project Structure

```
NovelTL_Dev/
├── backend/                 # FastAPI backend
│   ├── src/                # Source code
│   │   ├── auth/           # Authentication & users
│   │   ├── novels/         # Novel & chapter management
│   │   ├── labels/         # Manual label management
│   │   ├── autolabels/     # NER worker & caching
│   │   ├── filters/        # Label filtering pipeline
│   │   └── languages/      # Language metadata
│   ├── alembic/            # Database migrations
│   ├── scripts/            # Utility scripts (seeding, etc.)
│   └── tests/              # Pytest test suite
├── frontend/               # React + TypeScript frontend
│   └── src/
│       ├── components/     # Reusable UI components
│       ├── pages/          # Route-level pages
│       ├── api/            # API client functions
│       └── types/          # TypeScript type definitions
├── docs/                   # Comprehensive documentation
│   ├── README.md           # Documentation index
│   ├── architecture.md     # System architecture
│   ├── database-schema.md  # Database design
│   ├── api-design.md       # REST API patterns
│   ├── permissions.md      # Access control system
│   ├── background-jobs.md  # AutoLabel worker details
│   ├── filter-system.md    # Filter abstraction
│   ├── conventions.md      # Code style & naming
│   └── testing.md          # Testing guide
└── compose.yaml            # Docker orchestration
```

---

## 🛠️ Tech Stack

### Backend
- **FastAPI** - Modern Python web framework with auto-generated OpenAPI docs
- **SQLAlchemy** - ORM for PostgreSQL interactions
- **Alembic** - Database migration management
- **Pydantic** - Data validation and settings
- **ARQ** - Async Redis Queue for background tasks
- **PyTorch + Transformers** - NER model inference

### Frontend
- **React 19** - UI framework
- **TypeScript** - Type-safe JavaScript
- **Vite** - Build tool and dev server
- **Axios** - HTTP client with interceptors
- **React Router v7** - Client-side routing

### Infrastructure
- **PostgreSQL** - Primary database
- **Redis** - Task queue and caching
- **Docker Compose** - Multi-container development environment
- **Dev Containers** - Consistent development setup

---

## 📖 Documentation

Comprehensive documentation is available in the [`docs/`](docs/) directory:

- **[Architecture Overview](docs/architecture.md)** - System design and service interactions
- **[Database Schema](docs/database-schema.md)** - Tables, relationships, and design rationale
- **[API Design Guide](docs/api-design.md)** - REST patterns and endpoint conventions
- **[Permissions System](docs/permissions.md)** - Access control and visibility levels
- **[Background Jobs](docs/background-jobs.md)** - AutoLabel worker and state machine
- **[Filter System](docs/filter-system.md)** - Four-phase label filtering pipeline
- **[Conventions](docs/conventions.md)** - Code style and naming standards
- **[Testing Guide](docs/testing.md)** - How to write and run tests

**For new contributors**: Start with [docs/README.md](docs/README.md) for a guided tour.

---

## 🧪 Development

### Running Tests

```bash
# Run all tests
docker compose exec backend pytest

# Run with coverage
docker compose exec backend pytest --cov=backend/src --cov-report=html

# Run specific test file
docker compose exec backend pytest backend/tests/auth/test_auth.py
```

### Database Migrations

```bash
# Create a new migration
docker compose exec backend alembic revision --autogenerate -m "Description"

# Apply migrations
docker compose exec backend alembic upgrade head

# Rollback one migration
docker compose exec backend alembic downgrade -1
```

### Accessing Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f worker
```

### Stopping Services

```bash
# Stop all services
docker compose down

# Stop and remove volumes (WARNING: deletes database)
docker compose down -v
```

---

## 🔐 Default Credentials

After running `seed_admin.py`, use the credentials you entered during the interactive setup.

⚠️ **Choose a strong password for production deployments!**

---

## 🏗️ Current Status

**Backend**: ✅ Core features implemented
- User authentication (JWT)
- Novel & chapter management with permissions
- Label CRUD with overlap detection
- AutoLabel background processing
- Score filter implementation

**Frontend**: 🚧 In planning
- Component specifications documented in [docs/ui-requirements.md](docs/ui-requirements.md)
- React conventions defined in [docs/conventions.md](docs/conventions.md#frontend-naming-conventions)

**Known Issues**: See [GitHub Issues](https://github.com/lzguan/NovelTL_Dev/issues) for technical debt and planned improvements.

---

## 🤝 Contributing

1. Read the [conventions](docs/conventions.md) for code style guidelines
2. Check [GitHub Issues](https://github.com/lzguan/NovelTL_Dev/issues) for known bugs and planned features
3. Write tests for new features (see [testing.md](docs/testing.md))
4. Ensure migrations are included for schema changes

---

## 📝 License

[Add your license here]

---

## 🙏 Acknowledgments

Built with help from Claude (Anthropic) for documentation and architecture design.
