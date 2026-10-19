# FreshFirst Market

Create a FreshFirst application.

follow the spec

Centralize every backend call in one services layer,

and create a mock implementation of it so the

whole app runs without a real backend.

Add tests.

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/6cb9dff6-bb51-46af-ac03-9d288c2e416f).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>/frontend
npm ci
npm run dev
```

The frontend application and its configuration live in `frontend/`. Run all npm commands from that directory.

```sh
npm run build
npm test
npm run typecheck
npm run lint
npm run validate:api
```

`backend/` contains the FastAPI server. Project instructions and specifications remain in `AGENTS.md` and `docs/` at the repository root.

The npm workflow uses the tracked `frontend/package-lock.json`; `npm ci` installs its exact dependency tree. The old Bun lockfile has been removed to avoid competing dependency resolutions.

The frontend uses the real FastAPI backend through the typed `FreshService` HTTP adapter. Browser localStorage mock data is not used or migrated; the mock remains available only for isolated tests. `/basket` manages servings, confirmed substitutions and cooking; `/shopping` generates combined requirements, preserves manual lines, confirms overwriting edits and transfers confirmed purchases exactly once. Removing generated lines also requires confirmation on regeneration. Different pantry expiry dates require editing the existing entry before merging.

Root `openapi.yaml` defines 23 unauthenticated operations, request/response schemas, validation and conflict errors. `npm run validate:api` validates the OpenAPI document and checks one-to-one operation coverage against the typed service. The HTTP adapter maps the documented error envelope to `ServiceError`, including network and malformed-response failures.

The FastAPI backend implements all 23 operations with SQLAlchemy/SQLite persistence and a strict TheMealDB importer. See [backend startup, endpoint list and verification](backend/README.md). From `backend/`, run `uv sync --locked`, then `uv run uvicorn app.main:app --reload`. API docs are at `http://127.0.0.1:8000/docs`.

SQLite persists pantry, recipes, basket substitutions, shopping and cooking history across backend restarts. Set `DATABASE_URL` before startup (default `sqlite:///./freshfirst.db`, relative to the backend working directory). Tables and duplicate-safe catalog/rule seeds are created automatically; the previous in-memory state cannot be recovered after its process stops. See the backend README for setup and backups. The live import does not yet meet the 15–20 recipe target under the strict catalog/quantity rules; see the importer limitation in the backend README. TheMealDB has no serving yield, so imported `base_servings=1` denotes one complete source batch rather than an inferred human portion count.

## Run the integrated app

Start the backend from `backend/`:

```sh
uv sync --locked
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Then start the frontend from `frontend/`:

```sh
npm ci
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173`. Vite uses port 5173 with strict port checking; FastAPI allows CORS from `http://localhost:5173` and `http://127.0.0.1:5173`, including JSON mutation preflights. To change the API address, copy `frontend/.env.example` to `frontend/.env.local` and set `VITE_API_BASE_URL` to the complete API base URL (including `/api`), then restart Vite. There is no automatic mock fallback on backend failure. Startup imports recipes once; the Recipes import button explicitly retries importing.

Run `npm test` after `uv sync --locked`: the frontend suite starts and stops an isolated FastAPI subprocess on a free local port and exercises the actual TypeScript HTTP adapter through all 23 operations. It uses a strictly normalized synthetic source only within tests and requires the backend `.venv` Python executable. Set `FRESHFIRST_TEST_PYTHON` to override that executable. Other frontend tests retain their injected mocks. Run `uv run pytest -q` from `backend/` for the backend suite. See [integration verification](docs/integration.md) for results and limitations.
