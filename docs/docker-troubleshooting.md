# Docker & Dev Environment Troubleshooting

**Last Updated**: April 3, 2026  
**Status**: Complete

A log of Docker and Dev Container issues encountered during development, along with their root causes and fixes. Useful for anyone setting up the project on a new machine or debugging container startup failures.

---

## Table of Contents

1. [Concurrent Branch Isolation](#1-concurrent-branch-isolation)
2. [Postgres 18 Startup Crash](#2-postgres-18-startup-crash)
3. [Post-Create Command Permission Denied](#3-post-create-command-permission-denied)
4. [Git Shows All Files Modified](#4-git-shows-all-files-modified)
5. [Docker Build Permission Denied on uv.lock](#5-docker-build-permission-denied-on-uvlock)

---

## 1. Concurrent Branch Isolation

**Symptom:** Trying to open a feature branch in a Dev Container just re-opens the `main` branch container, or crashes due to `address already in use` (port collisions).

**Root Cause:** VS Code routes containers based on the local folder path. Docker Compose defaults to using the folder name as the project name, sharing the same network, ports, and volumes.

**Fix:**
1. Use **Git Worktrees** to check out the branch in a completely separate physical directory (`git worktree add ../feature-branch feature-branch`).
2. Add a `.env` file to the new directory with a unique `COMPOSE_PROJECT_NAME` (e.g., `noveltl_feature`).
3. In that `.env` file, shift all exposed host ports (e.g., `BACKEND_PORT=8001`, `FRONTEND_PORT=5174`).
4. Keep the internal container ports hardcoded to their defaults (e.g., `5432` for Postgres) so the internal network routes correctly without changing application code.

---

## 2. Postgres 18 Startup Crash

**Symptom:** Container crashes on boot with an error mentioning `/var/lib/postgresql/data (unused mount/volume)` and incompatible old data.

**Root Cause:** Postgres 18 updated its official Docker image path rules to prevent `pg_upgrade` boundary issues. Additionally, an older version's database files were still persisting in the named volume.

**Fix:**
- Change the target volume mount in `compose.yaml` from `/var/lib/postgresql/data` to the parent directory: `/var/lib/postgresql`.
- Delete the incompatible old volume entirely (`docker volume rm <volume_name>`) to force Postgres 18 to initialize a fresh, compatible database.

---

## 3. Post-Create Command Permission Denied

**Symptom:** Dev Container `postCreateCommand` fails with `mkdir: cannot create directory... Permission denied` when installing tools like Claude Code or Codex.

**Root Cause:** Named volumes (like `claude-code-config:/home/vscode/.claude`) are created and mounted by Docker as the `root` user. The installation script runs as the `vscode` user, which lacks write permissions to that root-owned directory.

**Fix:** Prepend a `sudo chown` command to take ownership of the mounted directories before running the install scripts:
```bash
sudo chown -R vscode:vscode /home/vscode/.claude /home/vscode/.codex && [install command]
```

---

## 4. Git Shows All Files Modified

**Symptom:** Running `git status` inside the Linux Dev Container shows every single file as modified, even right after a fresh clone. `git diff` shows `old mode 100644 new mode 100755` or entire lines replaced.

**Root Cause:** The host machine is Windows (NTFS / CRLF line endings) and the container is Linux (ext4 / LF line endings). Crossing the OS boundary mangles file execution permissions and carriage returns.

**Fix:** Add a `.gitattributes` file to the repo root to normalize line endings:
```
* text=auto eol=lf
```
This ensures all text files use LF endings regardless of the host OS. Git will handle the conversion automatically on checkout and commit.

**Alternative:** Clone the repository directly into the WSL filesystem (`~/projects/`) instead of mounting from `/mnt/c/`, and use VS Code's WSL remote extension before launching the Dev Container.

---

## 5. Docker Build Permission Denied on uv.lock

**Symptom:** Docker `build` fails during the `uv sync` step with `error: failed to write to file '/project/uv.lock': Permission denied (os error 13)`.

**Root Cause:** The `COPY` command in a Dockerfile runs as `root` by default. If a `uv.lock` file already exists on the host, it is copied in as a root-owned file. When the Dockerfile switches to `USER vscode` and runs `uv sync`, the package manager cannot overwrite the root-owned lockfile.

**Fix:** Explicitly set ownership during the copy step, before switching users:
```dockerfile
# Copy files AND assign ownership immediately
COPY --chown=vscode:vscode backend/pyproject.toml backend/uv.lock* ./

USER vscode

# Run sync (ensure cache is mounted to the user's home directory, not /root)
RUN --mount=type=cache,target=/home/vscode/.cache/uv,uid=1000,gid=1000 \
    uv sync --all-groups --no-install-project
```

---

## 6. Devcontainer Startup Failing on Reload Window in VSCode in Windows 11

**Fix:** Restart wsl.

## Relevant Files
- `compose.yaml` - Docker Compose service definitions
- `.devcontainer/devcontainer.json` - Dev Container configuration
- `.env.example` - Environment variable template
- `.gitattributes` - Line ending normalization rules

## See Also
- [architecture.md](architecture.md) - Deployment architecture overview
