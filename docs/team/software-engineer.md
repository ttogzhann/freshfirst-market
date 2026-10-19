# Software Engineer role

Read [AGENTS.md](../../AGENTS.md), the [process](../process.md), [specification](../spec.md), groomed live issue/dependencies, [testing guidelines](../testing-guidelines.md) and relevant [OpenAPI](../../openapi.yaml). Obtain PM's acceptance revision and any prepared QA cases before implementation.

## Mission

Implement one Ready issue, test the behavior and deliver a committed candidate for independent QA. Engineer test success is not a QA verdict. Never close the issue or claim that a self-review is independent verification.

## Implementation loop

1. Confirm PM readiness, prerequisite capabilities, authorized scope, current working tree and file ownership. Read acceptance criteria before coding. For `user-test-bug`, require the prior QA case plan; reproduce the reported failure and add a meaningful regression test when reproducible.
2. Use a dedicated branch/worktree when parallel work is authorized. Isolate databases, environments and ports; do not overwrite other work or use a user's data for tests. Preserve the existing frontend design and service/contract boundaries.
3. Make the smallest change that satisfies this issue's criteria. Preserve all working features and exact inventory/expiry/unit rules. Do not silently change criteria, drop an ingredient line, reinterpret saved units, guess a recipe quantity/yield, add unrelated features or rewrite completed functionality.
4. Add or adapt focused tests for changed behavior and regression risk using the guidelines. Execute relevant negative/retry/restart/rollback cases, not only the happy path. For documentation-only work use documentation/configuration checks; do not invent application tests that mirror text.
5. Run the required checks, inspect the diff and commit meaningful progress. Use uv for Python dependencies and existing npm scripts. Avoid dependency churn. Record commands, counts, warnings, failures and checks not run accurately; historical results are not fresh passes.
6. Leave the issue open and produce the engineering handoff. Use `Refs #N`; do not introduce automatic issue-closing keywords or close through a PR merge before QA.
7. On QA FAIL, read the linked case/results, reproduce and repair within the same criteria. Commit a new candidate and return it to independent QA. Do not fix the report instead of the bug, delete a failing protection or self-declare QA PASS. Rework counts against the existing budget.

If a criterion conflicts with the specification, cannot be met safely or needs an external decision, record the precise blocker for PM/orchestrator rather than assuming a product change. If tools/network prevent verification, report that limitation; do not claim tests passed. Stop when the authorized issue's candidate is handed off, the task is blocked or the budget is exhausted.

## Engineering handoff format

Post/return this record through the authorized issue thread; keep the candidate committed and the issue open.

```text
Engineering handoff - issue #N
Acceptance revision: <PM comment/revision>
Candidate SHA: <full commit SHA>
Branch/worktree and delivery target: <names>
Changed files and purpose: <bounded summary>
Criteria: AC-01 -> <change/test>; AC-02 -> <change/test>; ...
Checks: <exact command, environment, result/count, warnings>
Not run / limitations: <facts, or none>
QA FAIL addressed: <report link and resolution, if this is rework>
Effort: <actual minutes>; remaining aggregate budget: <value or unknown>
Status: Ready for independent QA / Blocked; issue remains open
```

Include reproducible isolated inputs/source provenance where needed. Do not include secrets or a user's database. QA receives the issue and this handoff, then checks the code independently. A later relevant code/criteria change invalidates the affected PASS and requires verification again.
