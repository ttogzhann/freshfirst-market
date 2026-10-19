# FreshFirst testing guidelines

Use with the [process](process.md), [task template](task-template.md) and [independent QA contract](team/qa-engineer.md). The specification and issue acceptance criteria define expected behavior; the implementation's current output is not the oracle. Existing test results are a baseline, not permission to claim an unexecuted check passed.

## Plan checks around the issue

Engineer maps each acceptance criterion to meaningful tests/direct observations. QA independently checks that mapping and adds missing cases, then records actual results. Focused regression coverage should prove user behavior or a data invariant rather than reproduce the implementation expression. Do not add speculative tests for unrelated features or unit tests that merely mirror a reversible documentation edit.

For `user-test-bug`, PM first captures the report; independent QA prepares mapped cases before engineering. Use a small case record: TC ID, AC ID, tested revision/environment, sanitized inputs/preconditions, steps, expected result, observed result and evidence. Demonstrate failure on the buggy revision when possible, then success on the fixed revision. A missing baseline or non-reproducible failure is a recorded gap, not an invented red/green demonstration.

For ordinary implementation, run focused checks while changing code, then the relevant backend/frontend suite before handing off. QA runs its required verification independently on the committed candidate. The final integrated MVP gate runs both full suites plus static/contract/build checks; do not substitute isolated branch passes for integration evidence. Avoid repeated broad checks after unchanged passing results unless new changes, failures or unresolved risks justify them.

## Isolation and reproducibility

- Use a disposable file-backed SQLite database for restart/rollback tests, with an absolute worktree-local `DATABASE_URL`; create its parent directory first. Never inspect or overwrite the user's active pantry database.
- Tests requiring process restart must reopen the same file, not `sqlite:///:memory:`. Separate processes/engines are needed to demonstrate persistence/concurrency; merely reusing an object is not that evidence.
- Each worktree gets its own environment, frontend install, generated files and ports. Respect existing CORS origins for browser checks; use supported origins or sequential browser runs rather than weakening production CORS to accommodate a test.
- Fix/inject the business date for expiry boundary tests. Record date/threshold, source provenance and environment so results can be reproduced across calendar days.
- Synthetic strictly quantified sources are valid for isolated service/HTTP tests. Only unaltered real source responses with verified quantities count toward the production recipe baseline; mock counts do not prove it. Do not silently use live network access in deterministic unit tests.
- Run the exact candidate SHA. Report command, working directory, input/setup, result/count and relevant warnings. Keep sensitive data out of issues, test output and source captures.

## Required domain checks when relevant

| Area                 | Evidence to preserve or add for changed behavior                                                                                                                                                             |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Pantry/units         | Positive finite quantities, compatible g/kg and ml/l units, exact supported kitchen-volume factors, valid dates, same-expiry merge and differing-expiry conflict without mutation                            |
| Expiry               | Yesterday excluded from all availability calculations; today/threshold boundary included; configured frontend/backend status agrees; expired entries remain editable                                         |
| Source import        | Every ingredient line accounted for, unsupported measures rejected, exact identities/dimensions, real raw provenance, stable external-ID upsert and no failed traversal partial writes                       |
| Baseline source seed | At least two real distinct valid records with shared stock, offline missing-ID initialization, repeat-safe seed and no overwrite of newer live records; this is remaining work, not an already passing claim |
| Scaling/substitution | Exact whole-batch multiplier 1-8 where yield is unknown, consistent requested/base ratio, explicit confirmation, rule eligibility and sufficient aggregate usable substitute stock                           |
| Basket/shopping      | Unique selection, saved choice preservation, shared demand aggregated once, stock subtracted once, manual lines/edit protection, truthful partial-update recovery                                            |
| Purchase             | Checkbox alone changes no inventory, actual quantity/expiry confirmation, atomic marker/merge, failed/conflicting transfer rollback, retry after restart adds stock only once                                |
| Cooking/history      | Revalidate after preview, aggregated demands, no negative/partial deductions, consumption snapshot with atomic history, SQL-write failure rollback and competing cook/transfer protection                    |
| Failure recovery     | Backend rejection preserves editable inputs; uncertain cooking response reconciles history/stock and never automatically retries a non-idempotent cook; no false success                                     |
| Contract/UI          | All 23 operation IDs/schemas/errors retained, HTTP adapter/CORS/empty responses, existing design and filters, usable responsive controls and loading/empty/error states                                      |

Do not declare the two-real-recipe baseline, batch-label fixes, recovery fixes or final browser acceptance complete merely because the previous 99 backend/47 frontend tests passed. Those counts describe the earlier implementation. The new candidate needs its own results. Full older-history browsing and the 15-20 source corpus remain optional Post-MVP; stored history/API/data integrity do not.

## Existing commands

Run backend commands from `backend/` using uv; dependency files and lockfiles are authoritative:

```sh
uv sync --locked
uv run --locked pytest -q
uv run --locked ruff check app tests
uv run --locked ruff format --check app tests
```

For a focused backend change, existing suites include `tests/test_validation.py`, `tests/test_calculations.py`, `tests/test_importer.py`, `tests/test_inventory_transactions.py`, `tests/test_persistence.py` and `tests/test_contract.py`. Select relevant tests explicitly, for example:

```sh
uv run --locked pytest -q tests/test_inventory_transactions.py tests/test_persistence.py
```

Run frontend commands from `frontend/` using the tracked npm lockfile:

```sh
npm ci
npm test
npm run typecheck
npm run validate:api
npm run lint
npm run build
```

Use `npm ci` when preparing an environment or changing the lockfile; do not reinstall for every unchanged test run. The frontend HTTP suite starts its own FastAPI subprocess and requires `backend/.venv` or the documented `FRESHFIRST_TEST_PYTHON` override. Focused suites include:

```sh
npm test -- src/services/httpService.integration.test.ts
npm test -- src/test/basket-shopping.test.tsx
```

The commands are independent checks: capture each exit status rather than treating the last successful command as proof all earlier ones passed. Pre-existing Fast Refresh/build/deprecation warnings must be recorded and distinguished from new regressions; a warning is not a failure unless it violates a criterion or required check. A failing required check cannot be waved through because a different suite is green.

## Documentation and workflow configuration changes

For Markdown-only changes, inspect the diff for unintended product/code changes and check:

1. Required documents exist and every local Markdown link/heading anchor resolves, including links from AGENTS.md and role handoffs.
2. PM/Engineer/QA responsibilities agree across files: four-section grooming, independent verification, FAIL returns to engineer, only the orchestrator closes after a current PASS, and user-bug cases precede implementation.
3. Test paths/commands match existing files, package scripts and backend project configuration. No invented commands, installed automation or historical QA claims.
4. Formatting passes using the existing frontend Prettier dependency on the changed documents only; `git diff --check` passes. Do not run a repository-wide formatter or add dependencies for this.
5. If GitHub configuration is part of the authorized task, verify the label name/description and unchanged issue states directly. Do not create issues or comments just to test documentation.

From the repository root, the existing formatter can check these workflow files:

```sh
node frontend/node_modules/prettier/bin/prettier.cjs --config frontend/.prettierrc --check AGENTS.md docs/process.md docs/task-template.md docs/team/pm.md docs/team/software-engineer.md docs/team/qa-engineer.md docs/testing-guidelines.md
git diff --check
```

The repository currently has no automated CI enforcement of these process rules. A Markdown link/structure check validates the instructions, not an application's functionality or an independent QA PASS. No backend/frontend full test rerun is required solely for prose changes; run contract validation when the change references the API/toolchain and record what actually ran.

## QA evidence and closure

Use the [QA verdict format](team/qa-engineer.md#verdict-format), with each AC marked PASS/FAIL, exact tested SHA/revision, observed results, commands/counts, skipped checks and actual effort. At least one unverified or failing criterion means **QA FAIL**; environment limitations are explicit blockers. QA does not repair tracked application/test/configuration files or alter criteria. Return failure evidence to engineering and re-verify the new candidate.

Only after a fresh independent **QA PASS** covering the delivered revision can the orchestrator close the issue. A changed criterion or relevant code after PASS needs re-verification. Preserve the 33 earlier retrospective closures as historical records without claiming they followed this workflow. Any newly reopened issue uses the new gate. Budget exhaustion leaves unfinished work open and honestly reported.
