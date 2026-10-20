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
