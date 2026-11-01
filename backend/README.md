# FreshFirst backend

FastAPI implements the 23 original domain operations in root `openapi.yaml`, plus registration, login, logout and session restoration. Account-bound API calls use opaque server-side sessions; the frontend auth integration is a separate milestone.

## Run locally

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run from the repository root:

```sh
cd backend
uv sync --locked
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Swagger UI: <http://127.0.0.1:8000/docs>. Contract: <http://127.0.0.1:8000/openapi.json>. All application state is stored in SQLite through SQLAlchemy. Reloading or restarting retains pantry, imported recipes, basket and substitutions, shopping edits and transfer flags, and cooking history.

For environments that require the operating system's certificate store, set `UV_SYSTEM_CERTS=true` before `uv sync` (PowerShell: `$env:UV_SYSTEM_CERTS = "true"`). The external recipe client uses Python's system trust configuration and never disables TLS verification.

The catalog contains 77 ingredient identities and ten context-limited substitution rules. Newly registered accounts start with empty pantry, basket, shopping list and cooking history. Existing ownerless personal records are preserved during migration but quarantined and inaccessible to every account; they are never assigned to the first registrant. `FRESHFIRST_EXPIRY_DAYS` sets the near-expiry threshold before startup; default is three days. Expired items remain visible but supply zero usable stock.

Configure matching frontend/backend thresholds before launch. For five days in PowerShell, set `$env:FRESHFIRST_EXPIRY_DAYS="5"` in the backend shell, and set `VITE_FRESHFIRST_EXPIRY_DAYS=5` in `frontend/.env.local` or the frontend shell environment. Restart both applications; rebuild production frontend assets after changing the Vite value. Both must match because this release has no configuration endpoint or automatic mismatch detection. Missing values default to 3; 0 includes today only. Supplied environment values must contain decimal digits only, from 0 through 9007199254740991 (the shared JavaScript exact-integer limit). Blank, negative, fractional, `NaN`, `Infinity` or nonnumeric values fail early with the variable name; injected `FreshService` thresholds are validated too. Today and the threshold day are inclusive; yesterday always supplies zero stock. This only changes urgency/status/counts and does not alter saved dates, stock availability or imply a food-safety guarantee.

Startup seeds only missing recipe IDs from 15 complete reviewed real TheMealDB responses packaged in `app/data/mealdb-source/`, including the unchanged original 53137 and 52776 captures. The provenance manifest records source URLs, capture timestamps and SHA-256 hashes; the original two raw files still match FF-18 captures in `tests/fixtures/mealdb-source/`, and all 15 match the reviewed captures and independent slot matrix in `tests/fixtures/mealdb-breadth/`. The same strict normalizer used for live import validates the entire package before any recipe is committed. Startup works offline without network traversal, never overwrites existing recipes, and fails visibly if packaged data is malformed. Recipe seeding creates no inventory. For these records, `base_servings=1` means the complete quantity set from one source recipe; it does not claim a human yield or portion count. A selected value of 1–8 scales whole source batches.

The explicit import endpoint fetches from the live TheMealDB service and therefore requires network access. It does not substitute the packaged seed or synthetic success when the source is unavailable. Normalization errors for individual source recipes are returned as skipped entries in a successful import report. Source traversal, network, or malformed-response failures instead return HTTP 502 with `SOURCE_UNAVAILABLE`; previously stored recipes and user state remain unchanged. The reviewed startup baseline and an explicit live import are separate operations:

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

## Authentication rate limits

Authentication uses fixed windows and returns HTTP `429` with the stable error code
`RATE_LIMITED` when a limit is exceeded:

- Registration: **5 attempts per client IP per hour**.
- Login: **20 attempts per client IP per 15 minutes** and **10 attempts per normalized account per
  15 minutes**. The account key is the trimmed, case-insensitive email identity used for login.

The `Retry-After` response header is the number of seconds remaining until the exceeded window(s)
reset and a retry may be permitted. These limits are enforced by the backend and do not depend on
the frontend.

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

The original MVP minimum was two verified real recipes sharing milk and sugar. The FF-20 implementation now ships 15 reviewed genuine recipes spanning Dessert, Miscellaneous, Pork, Side, Vegan and Vegetarian; independent acceptance status is recorded in [the source-breadth evidence](../docs/evidence/ff20-source-breadth.md). The historical 15–20 target was an internal breadth-planning target, not a university requirement. The importer can accept up to 20 distinct recipes, but that capacity does not mean the breadth target has been met. Cups without an exact supported definition, mass measured as tablespoons without a verified density, counts for mass-only ingredients, ranges, pinches, handfuls, package sizes and to-taste quantities remain unsupported. Quantities and human yields are never guessed.

The packaged startup corpus contains the 15 unaltered TheMealDB responses listed in `app/data/mealdb-source/provenance.json`, including original `53137.json` and `52776.json`. `app/data/mealdb-source/provenance.json` records their source lookup URLs, capture timestamps and SHA-256 hashes; the original two raw bytes match the FF-18 captures under `tests/fixtures/mealdb-source/`. All 15 are passed through the strict normalizer and seed only missing external IDs. A synthetic test payload is isolated to tests and is never a production recipe.

## Verify

```sh
uv run pytest -q
uv run ruff check app tests
uv run ruff format --check app tests
uv run python -m compileall -q app
```

Tests validate the authored OpenAPI document, compare registered operation IDs/methods/paths, and validate actual success and error responses against its schemas for all 27 operations (the original 23 domain operations plus four authentication operations). They cover input errors, matching, scaling, substitutions, expiry boundaries, basket aggregation, shopping edits, purchase idempotence, simultaneous inventory writes, rollback after injected failures, account/session lifecycle, CSRF, rate limits, two-account ownership isolation, migration preservation/quarantine and source failures. Unit/API tests use injected sources and do not need network access. Live importing is checked separately.

## SQLite setup, migration and backups

From `backend/`, install dependencies using `uv sync --locked`. Configure the URL in the server environment before starting Uvicorn. PowerShell example:

```powershell
$env:DATABASE_URL = "sqlite:///C:/path/to/freshfirst.db"
$env:FRESHFIRST_AUTH_SECRET = "replace with a stable secret of at least 32 bytes"
$env:FRESHFIRST_TRUSTED_ORIGINS = "http://localhost:5173"
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The default is `sqlite:///./freshfirst.db`, relative to the process working directory. Use the same URL and working directory after restart; changing them selects a different database. The parent directory must exist and be writable. SQLite files and journals are ignored by Git. `sqlite:///:memory:` is available for isolated tests only; omit it for durable storage. No `.env` loader is added: set the actual environment variable in your shell/process manager.

`FRESHFIRST_AUTH_SECRET` is required, must contain at least 32 bytes, and must remain identical across workers and restarts because it derives CSRF proofs. `FRESHFIRST_TRUSTED_ORIGINS` is a comma-separated allowlist of complete browser origins; wildcards are rejected. The local default allows `http://localhost:5173` and `http://127.0.0.1:5173`. Configure the real frontend origin in each deployment. Credentialed CORS is restricted to that list.

The server issues an HttpOnly, SameSite=Lax session cookie. HTTPS or `FRESHFIRST_ENV=production`/`prod` enables Secure cookies. Call `GET /api/auth/session` first to restore the current session and receive its CSRF token; send that token as `X-CSRF-Token` and the allowed `Origin` on registration/login and all mutations. Catalog, recipe content and substitution-rule reads are public; account-derived/matching endpoints and all mutations, including recipe import, require authentication. Passwords are hashed with Argon2id; raw session IDs and CSRF proofs are not persisted.

SQLite applies numbered migrations transactionally at startup. Migration v1 adds account/session tables and ownership columns, preserves existing ownerless personal rows as quarantined data, and replaces global pantry/basket uniqueness with owner-scoped constraints. New accounts are initialized with empty personal state. The remaining tables include the shared catalog/recipes/rules, cooking history and account-specific settings. Quantities use canonical-unit numeric columns; basket substitutions and history consumption snapshots use JSON. Catalog and reviewed substitution rules are seeded with conflict-safe inserts. Startup initializes the packaged missing-only recipe baseline through the strict TheMealDB normalizer; explicit live import upserts by unique external ID.

Existing browser mock/localStorage data is not migrated. Back up an existing SQLite database with the application stopped before changing schema or moving the file; restore it by pointing `DATABASE_URL` at the copied file. Do not delete an existing file to upgrade it; future incompatible schema changes require a new versioned migration.

SQLite serializes operations with a 30-second lock timeout. This is appropriate for the local single-user application. Keep the active database on a local disk; avoid simultaneous access to cloud-synced copies from different machines.

Persistence verification: `uv run pytest -q tests/test_persistence.py` checks a new Python process reading the same file, every persisted entity and shopping edit marker, repeated imports and transfer retries after restart, one-time seeds even after pantry deletion, rollback after SQL writes have already modified inventory, and concurrent cooks/transfers through six independent SQLAlchemy engines. The full suite also checks expired-stock exclusion, all 27 API operations and unchanged response schemas for the original domain operations.

Baseline verification: `uv run --locked pytest -q tests/test_offline_baseline.py` checks production bytes/provenance, exact quantities and metadata, offline default startup, separate-process restart, duplicate prevention, newer/extra recipes and user-state preservation, malformed-package rollback and explicit live-import failure. Existing strict negative tests remain in `tests/test_real_recipe_baseline.py`.
