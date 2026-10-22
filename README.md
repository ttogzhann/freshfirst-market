# FreshFirst Market

FreshFirst is a local, single-user recipe and pantry application. Its React/TypeScript
frontend communicates with a FastAPI backend over HTTP; SQLAlchemy and SQLite persist
pantry, recipes, basket selections, shopping changes, purchase transfers and cooking
history. The backend is the source of truth for recipe matching, quantities, shopping
and cooking calculations.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone https://github.com/ttogzhann/freshfirst-market.git
cd freshfirst-market/frontend
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

SQLite persists pantry, recipes, basket substitutions, shopping and cooking history across backend restarts. Set `DATABASE_URL` before startup (default `sqlite:///./freshfirst.db`, relative to the backend working directory). Tables and duplicate-safe catalog/rule seeds are created automatically. The earlier in-memory implementation had no disk state to recover; the current SQLite database persists across process restarts. Browser mock/localStorage data is not migrated. See the backend README for setup and backups. Offline startup seeds the two reviewed real TheMealDB recipes only when their IDs are missing; existing records are preserved. The 15–20 recipe breadth was an internal planning target and optional FF-20 expansion, not a university requirement or a completed result. TheMealDB has no serving yield, so imported `base_servings=1` denotes one complete source-recipe batch, not a human portion count.

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

Open `http://127.0.0.1:5173`. Vite uses port 5173 with strict port checking; FastAPI allows CORS from `http://localhost:5173` and `http://127.0.0.1:5173`, including JSON mutation preflights. To change the API address, copy `frontend/.env.example` to `frontend/.env.local` and set `VITE_API_BASE_URL` to the complete API base URL (including `/api`), then restart Vite. There is no automatic mock fallback on backend failure. Startup initializes missing reviewed baseline recipes offline; the Recipes import button makes a separate network-dependent live-source request. Source failures use the documented API error response (HTTP 502 `SOURCE_UNAVAILABLE`) and do not replace the offline seed or erase previously stored state.

The near-expiry threshold defaults to **3 days** in both applications. To use 5 days, set `$env:FRESHFIRST_EXPIRY_DAYS="5"` in the backend PowerShell before starting uvicorn and set `VITE_FRESHFIRST_EXPIRY_DAYS=5` in `frontend/.env.local` (or `$env:VITE_FRESHFIRST_EXPIRY_DAYS="5"` in the frontend shell) before starting Vite/building. **Both values must match**; restart the backend and Vite after changing them, and rebuild/reload production frontend assets because Vite embeds this value at build time. There is no runtime configuration negotiation.

Values must contain only decimal digits for a nonnegative whole-day integer. Missing values default to 3; **0 means today only**. Explicit blank, negative, fractional, `NaN`, `Infinity` or other text fail early with the responsible variable name (frontend dev/build and backend startup). The technical maximum is 9007199254740991, JavaScript's largest exact integer, shared by both apps; this is a numeric representation limit, not a recommended food-storage interval. The threshold includes today and the final configured day. Yesterday is always expired and supplies zero stock, while today is usable. Configuration changes urgency, badges and counts only, never stored expiry dates or food-safety guarantees.

Run `npm test` after `uv sync --locked`: the frontend suite starts and stops an isolated FastAPI subprocess on a free local port and exercises the actual TypeScript HTTP adapter through all 23 operations. It uses a strictly normalized synthetic source only within tests and requires the backend `.venv` Python executable. Set `FRESHFIRST_TEST_PYTHON` to override that executable. Other frontend tests retain their injected mocks. Run `uv run pytest -q` from `backend/` for the backend suite. See [integration verification](docs/integration.md) for results and limitations.

The owner's supplied partial original [brainstorming history](docs/brainstorming.md) preserves the earlier FreshRescue discussion and its original gaps; the current specification governs implementation.
