# NovelTL frontend

The frontend is a React and TypeScript single-page application built with Vite.
It provides a mostly read-oriented browsing surface and a stateful editing
workspace for chapters, labels, and autolabel results.

Start with the repository [documentation index](../docs/README.md),
[project structure](../docs/project-structure.md), and
[editor documentation](../docs/editor/README.md).

## Structure

The application is divided by responsibility:

- `src/view/` contains source-work and novel browsing pages;
- `src/edit/` contains the editor workspace, controller, managers, hooks, and
  CodeMirror integration;
- `src/auth/` contains authentication pages;
- `src/dashboard/` contains the landing dashboard;
- `src/components/` contains shared navigation, text, and UI components;
- `src/api/` contains generated API clients and models.

Routes are centralized in [`src/routes.ts`](src/routes.ts) and registered in
[`src/App.tsx`](src/App.tsx). The edit routes are lazy-loaded so the CodeMirror
and controller code is not part of the initial browsing bundle.

## UI conventions

The UI uses Tailwind CSS 4 and source-managed shadcn components built on Radix
primitives. Project configuration lives in [`components.json`](components.json)
and theme tokens live in [`src/index.css`](src/index.css).

Before building custom controls, check the components already installed under
`src/components/ui/`. Prefer component variants and semantic theme tokens over
page-specific copies or raw colors. The project uses Lucide for icons and the
`@/` alias for imports from `src/`.

## Backend client

FastAPI's committed OpenAPI schema is converted into TypeScript models, Fetch
clients, and Effect clients by Orval. Generated files under `src/api/models/`
and `src/api/endpoints/` should not be edited manually.

[`src/api/custom-fetch.ts`](src/api/custom-fetch.ts) attaches the stored access
token and normalizes responses for generated clients. Development requests to
`/api` are proxied to the backend by Vite.

See [scripts.md](../docs/scripts.md) for the complete regeneration workflow.

## Development

From the repository root:

```bash
pnpm --dir frontend dev
pnpm --dir frontend check
pnpm --dir frontend lint
pnpm --dir frontend format:check
pnpm --dir frontend test:ci
pnpm --dir frontend build
```

The devcontainer installs dependencies and supplies the default backend
hostname. Outside that environment, set `VITE_BACKEND_URL` when the backend is
not reachable at the Vite configuration's default address.

Vitest and Testing Library tests live beside the components and modules they
exercise. Browser-level workflows are kept in the repository's separate
[`e2e/`](../e2e/) Playwright project.

## Editor

The editor deliberately keeps its synchronization engine separate from React:

- the controller validates local actions, manages provisional IDs, and queues
  backend requests;
- managers translate between controller events and UI-facing state;
- hooks own the React state;
- CodeMirror renders and edits chapter text while the text model tracks label
  ranges.

This subsystem has additional invariants and vocabulary. Read
[`src/edit/README.md`](src/edit/README.md) and the
[editor documentation](../docs/editor/README.md) before making architectural
changes.
