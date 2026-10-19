# Frontend / FastAPI integration verification

## SQLite persistence verification - 2026-10-20

The backend now uses SQLAlchemy and SQLite with `DATABASE_URL`. All 23 operations and response schemas are unchanged; no frontend design or production service changes were needed.

- Backend: **99 tests passed**, including all 91 existing tests and eight file-backed persistence checks.
- A new Python subprocess reopened the same SQLite file and returned identical pantry (including expired entries), imported recipes, basket servings/confirmed substitutions, edited/generated/manual shopping lines, completed transfer flags and cooking history snapshots. Removed-generated-line edit protection also survived restart.
- Injected SQL failures after pantry writes rolled back both inventory and cooking history/transfer completion. Six independent engines serialized competing cooks and transfers: one successful cook per available batch, no negative stock and one pantry addition per purchased line.
- Repeated import after restart updated the existing external recipe ID and retained basket references. Catalog/rule seeds remained at 40/10 rows; deleting all pantry entries did not cause sample stock to reappear.
- Frontend: **47 tests passed**, including the production HTTP adapter journey through all 23 operations against SQLite-backed FastAPI. TypeScript, OpenAPI validation, ESLint and production build checks passed. Existing Fast Refresh/build/deprecation warnings remain.

Setup and initial schema instructions are in `backend/README.md`. The pre-existing live-source 15-20 recipe count limitation remains; normalization rules were preserved. No new live-source audit or browser walkthrough was performed for this storage change.

## Previous HTTP integration phase (historical)

Verified on 2026-10-20. The default frontend service is now HTTP, with the existing `FreshService` signatures unchanged. FastAPI remains the source of truth for matching, scaling, substitutions, basket aggregation, shopping requirements, purchase transfer and cooking deductions. The browser keeps presentation formatting and form validation. No SQLite/SQLAlchemy changes were made.

## Automated checks

- Backend: **91 tests passed**, including all 23 OpenAPI operations and calculation/transaction/import validation coverage.
- Frontend: **47 tests passed** in six files. This includes the real HTTP integration journey, CORS checks, transport errors and a deferred purchase confirmation test.
- TypeScript check, OpenAPI validation, frontend production build and backend Ruff checks pass.
- ESLint passes with six existing React Fast Refresh warnings in shared UI components. Build emits the existing large-chunk and tsconfig-path plugin notices. Backend tests emit a Starlette TestClient/httpx deprecation warning.

The real HTTP suite starts its own FastAPI server on a free port, sends requests through the production TypeScript adapter, and stops the server afterward. It covers every service operation, including encoded substitution query parameters, unit normalization, expired-stock exclusion, validation failures, shopping overwrite conflicts, idempotent purchase transfer, blocked cooking and successful atomic cooking/history updates. The integration source is a synthetic, exactly quantified test recipe passed through the unchanged strict importer, isolated to `backend/tests/http_server.py`.

## Browser walkthrough

Performed through an isolated headless Edge browser against Vite at `http://127.0.0.1:5173` and FastAPI at `http://127.0.0.1:8000`. Browser actions were driven through its local debugging connection. The server used the same deterministic test source as the HTTP suite; this verifies integration without depending on live TheMealDB availability or inventing production recipe records.

| Flow                                       | Observed result                                                                                                                                                                                    |
| ------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pantry create / edit / delete              | Added Pasta at 300 g, edited to 250 g; added and removed Eggs; added Heavy cream at 300 ml.                                                                                                        |
| Recipe listing / details                   | Integration pasta listed with 33% match and Milk/Butter missing; details and instructions displayed.                                                                                               |
| Scaling / substitutions                    | Changing to two servings returned 200 g Pasta, 200 ml Milk and 20 g Butter. Explicitly selecting cream substituted the 200 ml Milk demand.                                                         |
| Basket                                     | Added recipe, changed servings to one and back to two; totals updated from the backend. Selection and substitutions survived page reload. Removal showed the empty basket after confirmation.      |
| Shopping generation                        | Generated only the 20 g Butter shortage; existing pantry stock and the confirmed cream substitution were accounted for. Regeneration of a purchased line required explicit overwrite confirmation. |
| Purchase transfer                          | Checking purchased exposed the actual quantity/expiry form. Confirming 20 g Butter and its expiry added pantry stock; completed transfer remained visible after reload.                            |
| Cooking preview                            | Missing Butter disabled confirmation. After transfer, preview allowed cooking.                                                                                                                     |
| Cooking confirmation / dashboard / history | Successful cooking appeared in recent history with two servings; pantry became 50 g Pasta and 100 ml cream, with depleted Butter removed.                                                          |
| Conflict handling                          | Adding Pasta with a different expiry displayed the backend conflict message and kept the form open.                                                                                                |
| Backend outage / recovery                  | Stopping FastAPI displayed recoverable connection errors in Pantry. After restarting, Try again recovered and displayed the empty pantry expected from the in-memory store.                        |

## Remaining limitations

- State survives frontend refresh but resets on backend restart, as expected for this phase's in-memory store.
- The existing live importer does not meet the 15–20 supported-recipe target. This integration does not change ingredient mappings, quantity validation or conversion policy. See `backend/README.md` for the prior live-source audit. Live import was not repeated during this integration verification.
- Existing localStorage mock records are not migrated. Production requests never fall back to mock data after an API error.
- The browser walkthrough used a deterministic test source. It does not claim a full browser journey with the live external recipe source.
