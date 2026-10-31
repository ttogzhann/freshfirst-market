# FF43 engineering handoff - 2026-10-31

Acceptance: [FF43-PM-r1](https://github.com/ttogzhann/freshfirst-market/issues/43#issuecomment-6543850634), unchanged in the [PM handoff](ff43-pm-2026-10-31.md). Branch `feature/ff43-history`, isolated final worktree, based on delivered MVP `dc8957845af0402486b9eb115bb2e39d72a6a72e`. Candidate is the commit containing this record; exact SHA accompanies delivery. Issue remains open for independent QA.

## Changes and criteria

- AC-01/02: Dashboard delegates its recent-history section to `CookingHistory`. Default recent five remain supplied by Dashboard. The explicit View all cooking history control mounts the existing `useHistory` query only when opened; full results are copied and sorted newest-first by stored `cooked_at`. Every row retains stored title, a readable date/time with exact ISO `time` attribute, and unchanged neutral `recipeQuantity(record.servings)` semantics. No guessed yield or human portions.
- AC-03: mounted complete view has distinct visible loading, empty and actionable error/retry states using existing primitives. The toggle stays available to collapse during loading, errors or success; Dashboard stats and recommendations remain visible. Focused injected-service tests verify all states, full recovery and no mutating calls.
- AC-04: actual seven-cook browser/restart observations below demonstrate full durable records and unchanged related state. No storage/API behavior changes.
- AC-05: existing `useHistory` / `listHistory` / GET history operation reused without hook or service changes. Default collapsed view, sidebar, recommendations and stats preserved. Responsive stacked rows permit desktop/narrow keyboard browsing and return. No backend, API, schema, dependency, lockfile or generated route edits.

Owned implementation: `frontend/src/routes/index.tsx`, new `frontend/src/components/fresh/cooking-history.tsx`, new focused `frontend/src/test/cooking-history.test.tsx`. No ownership expansion was needed.

## Fresh checks

Windows, installed Node/npm and existing backend Python environment; no dependency changes. From `frontend/`:

- `npm test -- --maxWorkers=1 src/test/cooking-history.test.tsx`: 4 passed in 1 file, 2.62s. Deterministic seven-record fixtures verify default five/lazy request, unsorted full-input ordering, exact fields/neutral quantities, collapse, loading, empty and failure/retry/read-only behavior.
- `npm test -- --maxWorkers=1`: 93 passed in 13 files, 29.56s.
- `npm run typecheck`: passed.
- `npm run validate:api`: passed, all 23 operations match FreshService.
- `npm run lint`: passed, zero errors and six existing Fast Refresh warnings.
- `npm run build`: passed; existing tsconfig-paths advisory, chunk-size warning and ignored inlineDynamicImports warning.

Durable exact exits/logs: `.qa-state/ff43-engineer-matrix.json` and `ff43-engineer-{tests,typecheck,api,lint,build}.log`. Backend full suite was not repeated for this frontend-only feature; required actual backend restart was exercised directly. Markdown/local links and staged whitespace are checked before commit; cumulative archived transcript whitespace exception is unchanged.

## Seven real cooks, reload and process restart

Disposable actual FastAPI on 8002, supported frontend origin 127.0.0.1:5173 with process-only API URL 8002; no CORS edits. Database: absolute `backend/.qa-state/ff43-engineer-1793472917.sqlite`. Preserved existing 8000 listener and all earlier databases. Cleared only disposable sample pantry through API. Stocked exact genuine-source totals: milk 10630 ml, sugar 6675 g, baking powder 12.5 ml, vanilla 50 ml, chocolate 5250 g, butter 3675 g, eggs 105 pcs, flour 2625 g; expiry 2026-12-01.

Performed real preview/confirm API calls alternating genuine 53137/52776 at quantities 1,8,2,7,3,6,4. Seven distinct returned IDs `h_21` through `h_27` retained actual stored titles, timestamps, quantities and consumption. Browser used actual Edge at 1280x800 and 375x812: initial five, real Tab/Enter on open, seven rows newest-first, all titles/ISO times/neutral quantities checked against API, final row scrolled into view, visible keyboard focus, Space on collapse, five again, reload default collapsed. Document widths equaled 1280/375. Narrow full-page screenshot was visually inspected: all seven readable, no clipping, stats/recommendations intact.

Compared complete pantry/basket/shopping/history/recipe snapshots before and after browsing. Terminated owned API PID 30956, started PID 32176 against the same file, repeated both viewport flows and reload, and compared snapshots again: identical. SQLite integrity ok, no foreign-key violations, seven history/two genuine recipes retained; browsing introduced no mutations. Harness stopped only its own API/frontend.

Evidence: `.qa-state/ff43-engineer-runtime.json`, `ff43-engineer-browser-{before,restart}.json`, matching logs/screenshots and harness scripts. An earlier harness run encountered an occupied 5173 port and connected to another frontend; its four-row observation was not accepted as product evidence. Added an owned-process readiness check, confirmed ports free and reran successfully. No product change was made to accommodate that harness failure.

Status: Ready for independent QA on committed candidate. No push, merge, GitHub comment or closure. Actual and aggregate effort unknown. Independent reviewer must repeat all five criteria, including controlled real HTTP history failure/retry and viewport observations; engineering success is not a QA verdict.
