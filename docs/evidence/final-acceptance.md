# Final engineering acceptance evidence — 2026-10-20

Candidate application revision: `9c528ac` on `mvp/final-acceptance`, isolated
`freshfirst-market-final` worktree. This is engineering evidence, not independent QA PASS.
The original worktrees and their uncommitted changes were preserved.

| Check                                           | Actual result                                                        |
| ----------------------------------------------- | -------------------------------------------------------------------- |
| `uv sync --locked --link-mode copy`             | PASS; OneDrive hardlink mode initially failed, copy mode succeeded   |
| `uv run --locked pytest -q`                     | 153 passed in 63.06 seconds; one Starlette/httpx deprecation warning |
| `uv run --locked ruff check app tests`          | PASS                                                                 |
| `uv run --locked ruff format --check app tests` | PASS; 31 files                                                       |
| `npm ci`                                        | PASS; existing dependency deprecation warnings                       |
| `npm test -- --maxWorkers=1`                    | 89 passed, 12 files, 38.06 seconds                                   |
| `npm run typecheck`                             | PASS                                                                 |
| `npm run validate:api`                          | PASS; all 23 operations match FreshService                           |
| `npm run lint`                                  | PASS; zero errors, six existing Fast Refresh warnings                |
| `npm run build`                                 | PASS; existing route splitting/plugin advisories                     |

The first parallel frontend run passed 88 tests and exceeded the five-second timeout in
`expiry-config.test.tsx` for the three-day threshold. The complete serialized rerun above
passed without changing tests or product code. Lint initially rejected CRLF checkout
line endings; converting this isolated checkout to LF produced no substantive Git diff
and the lint rerun passed. No broad formatting changes were committed.

Backend startup succeeded against the disposable file-backed SQLite database
`backend/.qa-state/final-browser.db` on port 8001. Frontend Vite startup succeeded on
5174 using that API. Existing ports 8000 and 5173 were occupied and were preserved.
The supported CORS origins remain localhost/127.0.0.1 on 5173, so an unmodified browser
on 5174 needs a test harness or proxy; startup alone is not a browser walkthrough PASS.
Independent QA is responsible for its actual user workflow evidence and issue verdicts.

The backend suite includes persistence, atomicity, importer, HTTP contract and validation
coverage. The frontend suite includes the real HTTP adapter-to-FastAPI integration.
No fresh live TheMealDB source-success claim or manual browser PASS is made here.
Actual current engineering effort: approximately eight minutes wall time, including
integration, dependency setup, checks and this record; no historical effort is inferred.
Refs #46, #47 and #48. Issues remain open pending independent QA and orchestration.

## Engineering integration refresh — 2026-10-31 (FF48-PM-r1)

Tested committed revision: `f0f2820d686be59408b970cac6b066d48b9884ba`.
Delivery candidate is the subsequent documentation-only commit containing this record;
its full SHA accompanies the engineering handoff. Application/test/data/configuration
remain unchanged. Acceptance is preserved in [the PM refresh](ff48-pm-2026-10-22.md).
This is engineering evidence; fresh independent QA on delivery is still required.

| Command (backend or frontend working directory) | Actual result, exit 0                                                                                  |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `uv run --locked pytest -q`                     | 153 passed, 40.73s; one known Starlette/httpx deprecation warning                                      |
| `uv run --locked ruff check app tests`          | All checks passed                                                                                      |
| `uv run --locked ruff format --check app tests` | 31 files already formatted                                                                             |
| `npm test -- --maxWorkers=1`                    | 89 passed in 12 files, 39.11s                                                                          |
| `npm run typecheck`                             | Passed                                                                                                 |
| `npm run validate:api`                          | 23 operations match FreshService, no authentication                                                    |
| `npm run lint`                                  | Zero errors, six existing Fast Refresh warnings                                                        |
| `npm run build`                                 | Passed; existing tsconfig-paths advisory, large-chunk warning and ignored inlineDynamicImports warning |

Used installed uv at `C:/Users/User/AppData/Roaming/Python/Python312/Scripts/uv.exe`,
Python 3.12 backend environment and existing Node/npm installation; no dependency
changes. Earlier October 22 interrupted sessions expired without final retrievable
results; none are counted as passes. Fresh per-command logs and exact exits are in
`.qa-state/ff48-engineer-20261031-*.log` and the matching matrix JSON.

### Actual HTTP journey and same-file restart

Ran `.qa-state/ff48-engineer-journey.py` against actual Uvicorn/FastAPI on 8002,
absolute disposable SQLite file `backend/.qa-state/ff48-engineer-20261031b.sqlite`,
and actual Vite HTTP frontend on supported origin `http://127.0.0.1:5173` with
process-only API URL 8002. Headless Edge loaded both genuine recipe cards and
reloaded the page before and after backend restart. No production CORS edits.
The HTTP mutation journey used real API requests, not browser form actions; fresh
independent full UI/keyboard acceptance remains a separate required QA gate.

Startup supplied genuine external IDs 52776/53137. The first harness attempt
incorrectly assumed an empty initial pantry; existing first-run sample pantry is
intentional service behavior. Preserved that first disposable file and corrected
only the harness to clear sample items through the API in a new disposable file.
No product repair or fabricated production ingredient/source record was needed.

Added 100 ml milk with expiry 2026-12-01, selected both genuine recipes at one batch,
and generated exactly milk 930 ml (1030 combined demand minus 100 once), sugar
475 g, chocolate 250 g, butter 175 g, eggs 5 pcs, flour 125 g, baking powder
1.25 ml and vanilla 5 ml. Marking milk purchased alone left pantry unchanged.
Explicit actual-quantity/date confirmation transferred all eight lines; pantry
then held the complete combined demand, including milk 1030 ml.

Previewed and explicitly confirmed each one-batch cook. All stock quantities
reached zero and history contained exactly two records. Terminated the backend
process, started a new process using the same file, and compared complete pantry,
recipes, basket, shopping and history snapshots: identical. Recipe count remained
two and deleted sample pantry did not return. Repeating the already-transferred
milk purchase after restart left inventory unchanged. SQLite integrity check: ok.
Detailed output: `.qa-state/ff48-engineer-journey.json`; browser reload logs and
server logs retain actual observations. The harness stopped only its own servers.
Initial readiness HTTP probes produced Vite aborted-request diagnostics; the later
browser loads/reloads and all real API mutations succeeded.

Offline missing-only/no-overwrite and blocked-source semantics are additionally
covered by freshly passing `test_startup_http.py`, `test_offline_baseline.py` and
`test_importer.py`; no live import was performed in this engineer journey.
`test_inventory_transactions.py` and `test_persistence.py` cover rollback,
revalidation, independent connections, same-file processes and exactly-once transfer.
Source-backed tests verify exact raw provenance/normalization; substitution remains
separate fixture-only coverage, never a real-source substitution claim.

### Remaining independent gates

[#46 PASS](https://github.com/ttogzhann/freshfirst-market/issues/46#issuecomment-6340133326)
tested `0147990ac179dd7dd1817ef250554ee7b4bc7f04`;
[#47 PASS](https://github.com/ttogzhann/freshfirst-market/issues/47#issuecomment-6340220649)
tested `f0f2820d686be59408b970cac6b066d48b9884ba`.
Fresh independent #46 cases and final documentation/dependency review are required
on the delivery SHA; historical verdicts are not silently reattributed to it.
Compared with #44/#45 tested `f421b843`, backend source/data/tests are unchanged;
frontend application delta is only the report-route repair and its regression test;
OpenAPI delta is description wording. Full current checks supplement that bounded
applicability review, which QA must independently confirm.

Issue #48 remains open. No push, merge, deployment, GitHub edits or closure by the
engineer. #20/#43 remain separately authorized later work, not completed by this
MVP gate. All earlier evidence and transcript fidelity are preserved. Current and
aggregate effort ledger: unknown. Ready for independent QA after the evidence commit.
