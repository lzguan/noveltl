# Useful scripts

**Last updated:** 2026-05-10

Open postgres shell:
- Navigate to [`database/connection/`](../database/connection/)
- `chmod u+x connect_to_psql`
- `./connect_to_psql`

Create local db backup (basically just a wrapper around `pg_dump`)
- Navigate to [`database/db_backups/`](../database/db_backups/)
- `chmod u+x backup_db`
- `./backup_db`
- Saves `db` instance in [`compose.yaml`](../compose.yaml#L29) on the same compose network to [`database/db_backups`](../database/db_backups/)

Autogenerate client typescript files:
- Navigate to [`backend/`](../backend/)
- Run `uv run --no-sync -m scripts.extract_openapi_json`
- Navigate to [`frontend/`](../frontend/)
- Run `pnpm openapi-ts`

Seed database with admin data:
- Navigate to [`backend/`](../backend/)
- Run `uv run --no-sync -m scripts.seed_admin`
- Will prompt you for username/password.

Seed database with language data:
- Navigate to [`backend/`](../backend/)
- Run `uv run --no-sync -m scripts.seed_languages`

See [`frontend/package.json`](../frontend/package.json) for general frontend configurations and scripts.

See [`backend/pyproject.toml`](../backend/pyproject.toml) for general backend configurations and scripts.