# Coding agents

**Last updated:** 2026-05-10

We maintain project-specific agent guidance in [`.agents`](../.agents/), as
well as [`CLAUDE.md`](../CLAUDE.md) and [`AGENTS.md`](../AGENTS.md). Anyone who
wishes to use coding agents for this project can contribute improvements.

## Installing coding agents

### In a devcontainer

See [onboarding](onboarding.md) for devcontainer setup.

- [Claude code](https://code.claude.com/docs/en/quickstart)
    - `curl -fsSL https://claude.ai/install.sh | bash`
- [Codex](https://developers.openai.com/codex/cli): 
    - `pnpm setup`
    - Start a new shell
    - `pnpm add -g @openai/codex`.
    - `sudo apt update`.
    - `sudo apt install bubblewrap`.
- [Opencode](https://opencode.ai/docs/):
    - `curl -fsSL https://opencode.ai/install | bash`

### On local

Local setup not yet documented, we recommend using devcontainers for now. If you need to install on local, follow the instructions on the provider docs.
