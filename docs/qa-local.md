# Reproducible local QA

Run this from a clean checkout when validating the existing frontend-to-backend
integration. It creates or reuses only the ignored `backend/.venv`; it does not
need application secrets or a user database.

```powershell
$ErrorActionPreference = "Stop"
$uv = (Get-Command uv -ErrorAction Stop).Source

Push-Location backend
try { & $uv sync --locked } finally { Pop-Location }

Push-Location frontend
try {
  npm ci
  npm test
} finally { Pop-Location }
```

`uv sync --locked` must run before the frontend suite. The HTTP integration
tests start an isolated FastAPI subprocess using `backend/.venv/Scripts/python.exe`
on Windows (`backend/.venv/bin/python` elsewhere). To use an already prepared
environment explicitly, set `FRESHFIRST_TEST_PYTHON` to that Python executable
for the test process. The test suites use temporary SQLite databases and fixed
test-only credentials; no secrets are required.

If the integration suite reports that its backend process cannot start, first
confirm that the selected executable exists and rerun `uv sync --locked` from
`backend/`. Do not change product code or weaken the test to hide a missing
environment. Capture each command's exit status independently.

Issue #64 diagnosis on the frozen checkout: with the ignored `backend/.venv`
temporarily moved aside, `npm test -- --run
src/services/httpService.integration.test.ts` failed with `spawn
...backend\\.venv\\Scripts\\python.exe ENOENT` and reported 1 failed suite /
2 skipped tests. Restoring the directory and running `uv sync --locked` made
the same suite pass with 1 file and 2 tests. This establishes a missing
environment failure; the historical OneDrive hard-link note is not treated as
the cause of this reproduction.

For only the real HTTP adapter check after setup:

```powershell
Push-Location frontend
try { npm test -- --run src/services/httpService.integration.test.ts } finally { Pop-Location }
```
