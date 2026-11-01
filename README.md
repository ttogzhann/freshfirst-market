# FreshFirst Market

FreshFirst is a recipe and pantry application with per-account data isolation. Its
React/TypeScript frontend communicates with a FastAPI backend over HTTP; SQLAlchemy
and SQLite persist pantry, recipes, basket selections, shopping changes, purchase
transfers and cooking history. The backend is the source of truth for recipe matching,
quantities, shopping and cooking calculations.

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

The FastAPI backend implements the domain operations with SQLAlchemy persistence (SQLite by default, PostgreSQL when configured) and a strict TheMealDB importer. See [backend startup, endpoint list and verification](backend/README.md). From `backend/`, run `uv sync --locked`, then `uv run uvicorn app.main:app --reload`. API docs are at `http://127.0.0.1:8000/docs`.

SQLite persists pantry, recipes, basket substitutions, shopping and cooking history across backend restarts. Set `DATABASE_URL` before startup (default `sqlite:///./freshfirst.db`, relative to the backend working directory). Tables and duplicate-safe catalog/rule seeds are created automatically. The earlier in-memory implementation had no disk state to recover; the current SQLite database persists across process restarts. Browser mock/localStorage data is not migrated. See the backend README for setup and backups. Offline startup now seeds 15 reviewed genuine TheMealDB recipes only when their IDs are missing; existing records are preserved. The original two records remain unchanged as the historical MVP minimum. The 15–20 breadth target was internal planning, not a university requirement. See [current corpus and pending independent acceptance](docs/evidence/ff20-source-breadth.md). TheMealDB has no serving yield, so imported `base_servings=1` denotes one complete source-recipe batch, not a human portion count.

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

## Run the production container (Part 3, stage 1)

The frontend is TanStack Start with server-side rendering. Its production build is a Node/Nitro server, not a static site; the image builds it with the `node-server` preset and runs that server alongside FastAPI. A small same-origin gateway publishes only port `8000`, proxies `/api` to FastAPI, and sends browser routes/assets to the SSR server. No Vite development or preview server is used.

From the repository root, build the image and create a persistent SQLite volume:

```powershell
docker build -t freshfirst:local .
docker volume create freshfirst-data
$secret = python -c "import secrets; print(secrets.token_urlsafe(48))"
docker run --name freshfirst `
  --publish 8000:8000 `
  --mount source=freshfirst-data,target=/data `
  --env "DATABASE_URL=sqlite:////data/freshfirst.db" `
  --env "FRESHFIRST_AUTH_SECRET=$secret" `
  --env "FRESHFIRST_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000" `
  --env "FRESHFIRST_ENV=production" `
  freshfirst:local
```

Open `http://localhost:8000`. The image runs as an unprivileged user, exposes port `8000`, and has a `/healthz` check that requires both the SSR frontend and API to respond. `DATABASE_URL` defaults to the mounted `/data/freshfirst.db`. Supply a unique secret of at least 32 bytes at runtime; do not put it in a Dockerfile, image build argument, source file, or committed env file. Keep the same secret and named volume when recreating the container so persisted sessions and user data remain usable. `FRESHFIRST_TRUSTED_ORIGINS` must contain the exact browser origin(s); use `http://localhost:8000` for the local example and replace it with the real origin for a future TLS-terminated deployment. Only port `8000` is published; the internal Node SSR and FastAPI ports are loopback-only.

To verify persistence, register and log in, add a pantry item, and reload the page. Stop and remove only the container (`docker stop freshfirst; docker rm freshfirst`), then rerun the same `docker run` command with the same secret and `freshfirst-data` volume. The session and pantry item should restore. Do not remove the named volume. These commands do not configure Compose, HTTPS, cloud resources, or deployment; those require their own issues and authorization. Local development commands above remain unchanged.

## Run the production app with PostgreSQL (Part 3, stage 2)

Compose runs the existing production image as `app` and PostgreSQL 16 as `db`. It does not start Vite or any development server. PostgreSQL is private to the Compose network; only the app port is published.

From the repository root, create the ignored local environment file and replace both placeholder secrets:

```powershell
Copy-Item .env.example .env
notepad .env
docker compose up --build -d
docker compose ps
```

The `db` service must show `healthy` before the app starts, and the app must eventually show `healthy` after its SSR and API checks pass. Open `http://localhost:8000`. The app uses the same-origin production gateway, PostgreSQL through `DATABASE_URL`, and the configured `FRESHFIRST_AUTH_SECRET` for sessions and CSRF proofs.

Useful operational commands:

```powershell
docker compose logs --follow db app
docker compose stop
docker compose start
docker compose down
```

`docker compose down` preserves the named `freshfirst-postgres-data` volume. To recreate the containers and verify persistence, run `docker compose down`, then `docker compose up -d`; registered accounts, sessions and application data remain available when `.env` retains the same secret and database credentials. For an intentional test-only reset, use `docker compose down -v`; this permanently deletes the Compose PostgreSQL volume and all data in it. Never use that reset against a database containing user data.

The committed `.env.example` contains placeholders only. `.env` is ignored and must never be committed. Do not print `docker compose config` with live values, publish the `db` port, or put secrets in the Dockerfile, image build arguments, or source files. SQLite remains the default independent local-development option; Compose is optional and does not change the documented backend/frontend development commands.

The owner's supplied partial original [brainstorming history](docs/brainstorming.md) preserves the earlier FreshRescue discussion and its original gaps; the current specification governs implementation.
