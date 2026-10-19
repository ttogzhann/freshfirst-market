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

The frontend uses a centralized `FreshService` mock with browser localStorage persistence. `/basket` manages servings, confirmed substitutions and cooking; `/shopping` generates combined requirements, preserves manual lines, confirms overwriting edits and transfers confirmed purchases exactly once. Removing generated lines also requires confirmation on regeneration. Different pantry expiry dates require editing the existing entry before merging.

Root `openapi.yaml` defines 23 unauthenticated operations, request/response schemas, validation and conflict errors. `npm run validate:api` validates the OpenAPI document and checks one-to-one operation coverage against the typed service. A future HTTP adapter must map the documented error envelope to `ServiceError`.

The FastAPI backend implements all 23 operations with a seeded in-memory store and a strict TheMealDB importer. See [backend startup, endpoint list and verification](backend/README.md). From `backend/`, run `uv sync --locked`, then `uv run uvicorn app.main:app --reload`. API docs are at `http://127.0.0.1:8000/docs`.

The frontend remains connected to its mock. HTTP integration and SQLite/SQLAlchemy persistence are deferred. In-memory data resets on backend restart. The live import does not yet meet the 15–20 recipe target under the strict catalog/quantity rules; see the importer limitation in the backend README. TheMealDB has no serving yield, so imported `base_servings=1` denotes one complete source batch rather than an inferred human portion count.
