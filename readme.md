Automated translation platform for Chinese webnovels. Contains a suite of tools to assist in translations:
- Automated text labeller
- Automated glossary builder
- Manual review tools to ensure labelling accuracy

## Getting started

1. Clone the repository.
2. Copy `.env.example` into `.env` and configure the indicated variables.
3. Run `docker compose up -d`.
4. To enable automated text labelling, run `docker compose up -d worker`.
5. Run `docker compose exec -it backend uv run python -m scripts.seed_admin`
6. In the same folder, run `docker compose exec -it backend uv run python -m scripts.seed_languages`.
7. Navigate to `localhost:5173` and log in.

Alternatively, 

1. Open the project in VSCode.
2. Copy `.env.example` into `.env` and configure the indicated variables.
3. Open the project in a devcontainer.
4. To enable automated text labelling, run `docker compose up -d worker` in the local shell.
4. In the devcontainer, navigate to `backend/` and run `uv run python -m scripts.seed_admin`. Enter a username/password.
5. In the same folder, run `uv run python -m scripts.seed_languages`.
6. Navigate to `localhost:5173` and log in.

Please read the docs or raise an issue if you have trouble with the instructions.

## Coming eventually

- Better tooling for manual review
- One-click automated novel translation

## Contributing

Please read the docs/code.