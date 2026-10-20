# FreshFirst backend

FastAPI implements the 23 operations in root `openapi.yaml`, under `/api`, with no authentication. The frontend uses this server through its existing typed HTTP service.

## Run locally

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run from the repository root:

```sh
cd backend
uv sync --locked
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Swagger UI: <http://127.0.0.1:8000/docs>. Contract: <http://127.0.0.1:8000/openapi.json>. All application state is stored in SQLite through SQLAlchemy. Reloading or restarting retains pantry, imported recipes, basket and substitutions, shopping edits and transfer flags, and cooking history.

For environments that require the operating system's certificate store, set `UV_SYSTEM_CERTS=true` before `uv sync` (PowerShell: `$env:UV_SYSTEM_CERTS = "true"`). The external recipe client uses Python's system trust configuration and never disables TLS verification.

The catalog contains 41 ingredient identities and ten context-limited substitution rules. Twelve sample pantry entries are seeded once per database relative to the initial local date, including an expired entry. Deleting all pantry entries does not re-seed them on restart. `FRESHFIRST_EXPIRY_DAYS` sets the near-expiry threshold before startup; default is three days. Expired items remain visible but supply zero usable stock.

Startup seeds only missing recipe IDs from two complete reviewed real TheMealDB responses packaged in `app/data/mealdb-source/` (53137 and 52776). The provenance manifest records source URLs, capture timestamps and SHA-256 hashes; raw bytes match FF-18 captures in `tests/fixtures/mealdb-source/`. The same strict normalizer used for live import validates the entire package before any recipe is committed. Startup works offline without network traversal, never overwrites existing recipes, and fails visibly if packaged data is malformed. Recipe seeding creates no inventory. Explicit live import requires connectivity:

```sh
curl -X POST http://127.0.0.1:8000/api/recipes/import
```

## Implemented operations

| Method | Path (after `/api`)                            | Operation ID            |
| ------ | ---------------------------------------------- | ----------------------- |
| GET    | `/ingredients`                                 | `listIngredients`       |
| GET    | `/substitution-rules`                          | `listSubstitutionRules` |
| GET    | `/pantry`                                      | `listPantry`            |
| POST   | `/pantry`                                      | `createPantryItem`      |
| PUT    | `/pantry/{id}`                                 | `updatePantryItem`      |
| DELETE | `/pantry/{id}`                                 | `deletePantryItem`      |
| GET    | `/recipes`                                     | `listRecipes`           |
| GET    | `/recipes/{id}`                                | `getRecipe`             |
| POST   | `/recipes/import`                              | `importRecipes`         |
| GET    | `/basket`                                      | `getBasket`             |
| POST   | `/basket/items`                                | `addToBasket`           |
| PATCH  | `/basket/items/{id}`                           | `updateBasketItem`      |
| DELETE | `/basket/items/{id}`                           | `removeBasketItem`      |
| GET    | `/shopping-list`                               | `getShoppingList`       |
| POST   | `/shopping-list/generate`                      | `generateShoppingList`  |
| POST   | `/shopping-list/items`                         | `addShoppingItem`       |
| PATCH  | `/shopping-list/items/{id}`                    | `updateShoppingItem`    |
| DELETE | `/shopping-list/items/{id}`                    | `removeShoppingItem`    |
| POST   | `/shopping-list/items/{id}/transfer-to-pantry` | `transferToPantry`      |
| POST   | `/cooking/preview`                             | `previewCook`           |
| POST   | `/cooking/confirm`                             | `confirmCook`           |
| GET    | `/cooking/history`                             | `listHistory`           |
| GET    | `/dashboard`                                   | `getDashboard`          |

Create/merge pantry and basket operations return 200; manual shopping creation and confirmed cooking return 201; deletes return an empty 204. Errors use `{status, code, message}` for 404, 409, 422, 500 and source-failure 502 responses as specified. Recipe detail accepts a URL-encoded JSON `substitutions` array and optional servings 1–8. `GET /recipes` supports query, category and match/title sorting.

## Calculations and transactions

- Models validate positive finite quantities, calendar dates, nonblank required text, compatible units and integer servings 1–8. Omitted patch fields are unchanged; explicit null is rejected where the contract does not allow it.
- Decimal arithmetic normalizes g/kg, ml/l and pcs. The explicit kitchen-volume table is 1 tsp = 5 ml and 1 tbsp = 15 ml. Fractions and mixed fractions are supported. Quantities are rounded half-up to two decimals; amounts rounding to zero are rejected rather than treated as free ingredients. Mass, volume and count are never interchanged.
- Matching uses adequate original ingredient lines at base servings; urgency breaks equal-score ties. Confirmed choices affect scaled demand, shopping and cooking, but never inflate the unapproved match score. Rules have explicit category eligibility; suggestions require compatible units and enough non-expired stock, including other demands for the same substitute. New basket substitution choices are checked before saving.
- Basket insertion updates an existing selection rather than duplicating it. Shopping aggregates the entire basket, applies its confirmed substitutions and subtracts usable pantry stock once per ingredient.
- Regeneration preserves manual entries unless `resetAll=true`. Edited, purchased or removed generated entries, or deletion of manual entries by reset, require confirmation with `force=true`. Purchase checkboxes alone never modify the pantry.
- Transfer requires a catalog-linked purchased line, actual canonical quantity and expiry date. Its completion flag and pantry merge are atomic and repeated requests cannot add stock twice. Any differing stored expiry date returns `EXPIRY_CONFLICT`, including expired entries, so the existing entry must be edited first.
- Each operation loads a transaction-local working set from SQLite and writes only changed rows through SQLAlchemy Core. `BEGIN IMMEDIATE` reserves the SQLite writer before stock is read, serializing independent connections/processes; a local `RLock` also protects shared test connections. Database exceptions roll back all SQL changes, including ID allocation and shopping edit flags. Foreign keys, unique ingredient/external recipe/basket recipe constraints, and nonnegative inventory checks provide database-level safeguards. Cooking rechecks current aggregate demands inside that transaction, rejects shortages without deductions, removes depleted entries and writes consumption history atomically. Returned values are detached copies. Concurrent purchases and cooks cannot double-transfer or make stock negative.

## Import policy and current limitation

The adapter uses the [official TheMealDB V1 first-letter search API](https://www.themealdb.com/api.php), with the documented development key, to discover candidates. It stops after 20 distinct accepted recipes, validates every required ingredient, normalizes only explicit supported quantities, and upserts by source ID without deleting previously imported recipes. A network or malformed-source failure returns 502 and commits none of that attempt. Unsupported recipes appear in `skipped` with their source ID, title and reason. Import does not run on page reads.

TheMealDB does not supply serving yields. `base_servings=1` explicitly means **one complete source-recipe batch**, not an inferred number of human portions. Requested servings multiply that batch consistently. A verified per-source yield mapping is needed before promising portion counts.

The MVP baseline is two verified real recipes sharing milk and sugar. Expansion to 15-20 supported recipes is Post-MVP FF-20. Cups without an exact supported definition, mass measured as tablespoons without a verified density, counts for mass-only ingredients, ranges, pinches, handfuls, package sizes and to-taste quantities remain unsupported. Quantities and human yields are never guessed.

Two unaltered TheMealDB responses captured during verification are stored in `tests/fixtures/mealdb.json` for offline import tests (source IDs 53137 and 52768, retrieved 2026-10-20). Synthetic test payloads are isolated to tests and are never used as production recipes.

## Verify

```sh
uv run pytest -q
uv run ruff check app tests
uv run ruff format --check app tests
uv run python -m compileall -q app
```

Tests validate the authored OpenAPI document, compare registered operation IDs/methods/paths, and validate actual success and error responses against its schemas for all 23 operations. They cover input errors, matching, scaling, substitutions, expiry boundaries, basket aggregation, shopping edits, purchase idempotence, simultaneous inventory writes, rollback after injected failures, source normalization/upserts and source failures. Unit/API tests use injected sources and do not need network access. Live importing is checked separately.

## SQLite setup, migration and backups

From `backend/`, install dependencies using `uv sync --locked`. Configure the URL in the server environment before starting Uvicorn. PowerShell example:

```powershell
$env:DATABASE_URL = "sqlite:///C:/Users/User/OneDrive/FreshFirst/freshfirst-market/backend/freshfirst.db"
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The default is `sqlite:///./freshfirst.db`, relative to the process working directory. Use the same URL and working directory after restart; changing them selects a different database. The parent directory must exist and be writable. SQLite files and journals are ignored by Git. `sqlite:///:memory:` is available for isolated tests only; omit it for durable storage. No `.env` loader is added: set the actual environment variable in your shell/process manager.

This is the initial SQLite schema: SQLAlchemy creates the tables automatically on startup. No separate migration command is required. The model includes the eight specification tables plus `store_settings` for durable ID allocation, the one-time pantry seed marker, and removed-generated-line edit protection. Quantities use canonical-unit numeric columns; basket substitutions and history consumption snapshots use JSON. API field names remain unchanged. Catalog and reviewed substitution rules are seeded with conflict-safe inserts. Startup initializes the packaged missing-only baseline through the strict TheMealDB normalizer; explicit live import upserts by unique external ID. No synthetic production recipes are added. Offline restarts preserve all existing recipes and saved state.

The former in-memory store has no disk data to migrate. Existing browser mock/localStorage data is also not migrated. Back up an existing SQLite database with the application stopped before changing schema or moving the file; restore it by pointing `DATABASE_URL` at the copied file. `create_all` initializes missing tables but is not an upgrade engine for future schema changes. Future incompatible schema changes require an explicit versioned migration; do not delete an existing file to upgrade it.

SQLite serializes operations with a 30-second lock timeout. This is appropriate for the local single-user application. Keep the active database on a local disk; avoid simultaneous access to cloud-synced copies from different machines.

Persistence verification: `uv run pytest -q tests/test_persistence.py` checks a new Python process reading the same file, every persisted entity and shopping edit marker, repeated imports and transfer retries after restart, one-time seeds even after pantry deletion, rollback after SQL writes have already modified inventory, and concurrent cooks/transfers through six independent SQLAlchemy engines. The full suite also checks expired-stock exclusion, all 23 API operations and unchanged response schemas.

Baseline verification: `uv run --locked pytest -q tests/test_offline_baseline.py` checks production bytes/provenance, exact quantities and metadata, offline default startup, separate-process restart, duplicate prevention, newer/extra recipes and user-state preservation, malformed-package rollback and explicit live-import failure. Existing strict negative tests remain in `tests/test_real_recipe_baseline.py`.
