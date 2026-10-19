# FreshFirst backend

FastAPI implements the 23 operations in root `openapi.yaml`, under `/api`, with no authentication. The frontend still uses its existing mock and has not been connected to this server.

## Run locally

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run from the repository root:

```sh
cd backend
uv sync --locked
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Swagger UI: <http://127.0.0.1:8000/docs>. Contract: <http://127.0.0.1:8000/openapi.json>. Use **one worker**: the store is local to one process. Reloading or restarting discards pantry, basket, shopping and history changes and starts a new seed. There is no SQLite, SQLAlchemy or disk persistence in this phase.

For environments that require the operating system's certificate store, set `UV_SYSTEM_CERTS=true` before `uv sync` (PowerShell: `$env:UV_SYSTEM_CERTS = "true"`). The external recipe client uses Python's system trust configuration and never disables TLS verification.

The catalog contains 40 ingredient identities and ten context-limited substitution rules. Twelve sample pantry entries are seeded relative to the current local date, including an expired entry. `FRESHFIRST_EXPIRY_DAYS` sets the near-expiry threshold before startup; default is three days. Expired items remain visible but supply zero usable stock.

Startup performs one TheMealDB import. Initial recipe import requires connectivity; there is no hand-entered production recipe seed or fallback to the frontend fixtures. On source failure the server remains available, logs the failure and keeps any recipes already in the current process. Retry explicitly:

```sh
curl -X POST http://127.0.0.1:8000/api/recipes/import
```

## Implemented operations

| Method | Path (after `/api`) | Operation ID |
| --- | --- | --- |
| GET | `/ingredients` | `listIngredients` |
| GET | `/substitution-rules` | `listSubstitutionRules` |
| GET | `/pantry` | `listPantry` |
| POST | `/pantry` | `createPantryItem` |
| PUT | `/pantry/{id}` | `updatePantryItem` |
| DELETE | `/pantry/{id}` | `deletePantryItem` |
| GET | `/recipes` | `listRecipes` |
| GET | `/recipes/{id}` | `getRecipe` |
| POST | `/recipes/import` | `importRecipes` |
| GET | `/basket` | `getBasket` |
| POST | `/basket/items` | `addToBasket` |
| PATCH | `/basket/items/{id}` | `updateBasketItem` |
| DELETE | `/basket/items/{id}` | `removeBasketItem` |
| GET | `/shopping-list` | `getShoppingList` |
| POST | `/shopping-list/generate` | `generateShoppingList` |
| POST | `/shopping-list/items` | `addShoppingItem` |
| PATCH | `/shopping-list/items/{id}` | `updateShoppingItem` |
| DELETE | `/shopping-list/items/{id}` | `removeShoppingItem` |
| POST | `/shopping-list/items/{id}/transfer-to-pantry` | `transferToPantry` |
| POST | `/cooking/preview` | `previewCook` |
| POST | `/cooking/confirm` | `confirmCook` |
| GET | `/cooking/history` | `listHistory` |
| GET | `/dashboard` | `getDashboard` |

Create/merge pantry and basket operations return 200; manual shopping creation and confirmed cooking return 201; deletes return an empty 204. Errors use `{status, code, message}` for 404, 409, 422, 500 and source-failure 502 responses as specified. Recipe detail accepts a URL-encoded JSON `substitutions` array and optional servings 1–8. `GET /recipes` supports query, category and match/title sorting.

## Calculations and transactions

- Models validate positive finite quantities, calendar dates, nonblank required text, compatible units and integer servings 1–8. Omitted patch fields are unchanged; explicit null is rejected where the contract does not allow it.
- Decimal arithmetic normalizes g/kg, ml/l and pcs. The explicit kitchen-volume table is 1 tsp = 5 ml and 1 tbsp = 15 ml. Fractions and mixed fractions are supported. Quantities are rounded half-up to two decimals; amounts rounding to zero are rejected rather than treated as free ingredients. Mass, volume and count are never interchanged.
- Matching uses adequate original ingredient lines at base servings; urgency breaks equal-score ties. Confirmed choices affect scaled demand, shopping and cooking, but never inflate the unapproved match score. Rules have explicit category eligibility; suggestions require compatible units and enough non-expired stock, including other demands for the same substitute. New basket substitution choices are checked before saving.
- Basket insertion updates an existing selection rather than duplicating it. Shopping aggregates the entire basket, applies its confirmed substitutions and subtracts usable pantry stock once per ingredient.
- Regeneration preserves manual entries unless `resetAll=true`. Edited, purchased or removed generated entries, or deletion of manual entries by reset, require confirmation with `force=true`. Purchase checkboxes alone never modify the pantry.
- Transfer requires a catalog-linked purchased line, actual canonical quantity and expiry date. Its completion flag and pantry merge are atomic and repeated requests cannot add stock twice. Any differing stored expiry date returns `EXPIRY_CONFLICT`, including expired entries, so the existing entry must be edited first.
- Every store operation holds an `RLock`, snapshots state and rolls back on exceptions. Cooking rechecks current aggregate demands inside that transaction, rejects shortages without deductions, removes depleted entries and writes consumption history atomically. Returned values are detached copies. Concurrent purchases and cooks cannot double-transfer or make stock negative.

## Import policy and current limitation

The adapter uses the [official TheMealDB V1 first-letter search API](https://www.themealdb.com/api.php), with the documented development key, to discover candidates. It stops after 20 distinct accepted recipes, validates every required ingredient, normalizes only explicit supported quantities, and upserts by source ID without deleting previously imported recipes. A network or malformed-source failure returns 502 and commits none of that attempt. Unsupported recipes appear in `skipped` with their source ID, title and reason. Import does not run on page reads.

TheMealDB does not supply serving yields. `base_servings=1` explicitly means **one complete source-recipe batch**, not an inferred number of human portions. Requested servings multiply that batch consistently. A verified per-source yield mapping is needed before promising portion counts.

**The 15–20 supported-recipe acceptance target is not currently met by the live data with this catalog and strict normalization.** The initial audit fetched 790 source recipes and accepted one; unsupported identities, quantities and dimensions were reported instead of guessed. Cups without an exact supported definition, mass measured as tablespoons without a verified density, counts for mass-only ingredients, ranges, pinches, handfuls, package sizes and “to taste” are rejected. Reaching the target requires reviewed source-specific identity/quantity mappings or a different supported source subset; the implementation does not invent conversions or recipe records to satisfy the count.

Two unaltered TheMealDB responses captured during verification are stored in `tests/fixtures/mealdb.json` for offline import tests (source IDs 53137 and 52768, retrieved 2026-10-20). Synthetic test payloads are isolated to tests and are never used as production recipes.

## Verify

```sh
uv run pytest -q
uv run ruff check app tests
uv run ruff format --check app tests
uv run python -m compileall -q app
```

Tests validate the authored OpenAPI document, compare registered operation IDs/methods/paths, and validate actual success and error responses against its schemas for all 23 operations. They cover input errors, matching, scaling, substitutions, expiry boundaries, basket aggregation, shopping edits, purchase idempotence, simultaneous inventory writes, rollback after injected failures, source normalization/upserts and source failures. Unit/API tests use injected sources and do not need network access. Live importing is checked separately.
