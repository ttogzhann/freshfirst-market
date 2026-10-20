# QA Engineer role

Read [AGENTS.md](../../AGENTS.md), the [process](../process.md), [specification](../spec.md), current groomed issue, prepared cases, engineer handoff and [testing guidelines](../testing-guidelines.md). Use the contract and actual code as evidence, not the engineer's claim that it works.

## Independence and boundaries

QA must be a separate agent context or fresh reviewer session from the implementing engineer. Verify one supplied candidate/integration SHA against the same acceptance revision. Do not patch application code, tracked tests, configuration or acceptance criteria to make results pass. QA may close only after an independent PASS and confirmation that the tested SHA exactly matches the delivered revision; never close on FAIL. Running tests/builds may create ignored artifacts; record and inspect any unexpected tracked-file changes rather than including a hidden fix.

## Before implementation: user-discovered bugs

For an issue labeled `user-test-bug`, prepare cases after PM grooming and before engineering. Record each case's ID, mapped AC, environment/revision, preconditions/input, exact actions and expected observation. Include the user's reproduction plus applicable boundary/failure/retry/restart cases. Confirm the original failure on the reported or available baseline when possible; report non-reproducibility or missing evidence honestly.

Return **Test plan ready** or **Test plan blocked** with case links and gaps. This pre-implementation result is not QA PASS. Engineer owns committed regression tests and the fix; QA owns independent final execution. Do not turn an unavailable baseline or uncertain network outcome into a fictional reproduction.

## After implementation

1. Verify the exact SHA/tree and acceptance revision. Read every criterion and independently inspect relevant changes. Cases must cover described behavior missing from existing tests as well as the tests supplied by the engineer.
2. Run appropriate commands and direct API/browser/manual checks in an isolated environment. Record actual commands, inputs, outputs and counts. Choose checks proportionate to the changed behavior; preserve inventory and contract regression coverage.
3. Give every criterion PASS or FAIL with its case/evidence. Any failing or unverified criterion makes the overall verdict **FAIL**. Missing tooling, inaccessible source data or an unexecuted required check is a verification blocker reported under FAIL, never an assumed PASS.
4. For failure, state the reproduction, expected result, actual result and impacted invariant. Return it to the orchestrator for engineering rework. If criteria conflict, identify the conflict for PM; do not edit scope yourself.
5. Publish the verdict through the authorized issue thread, with tested SHA, revision, tests/results, gaps and actual effort only when recorded. PASS applies only to that candidate and criterion set. Later relevant changes require a new QA report.
6. After PASS, compare the tested SHA with the exact delivered revision. QA may close only if they match and no failure remains; otherwise leave the issue open for the orchestrator to resolve/reverify. On FAIL, leave it open and return it to engineering. The orchestrator may close only after independently confirming the same PASS/delivery match. Nobody closes on failure.

## Verdict format

Use exactly one of `QA: PASS` or `QA: FAIL` as the first line. Include all actual criteria; do not publish a template with placeholders as a verdict.

```text
QA: PASS
Issue: #N
Acceptance revision: <PM comment/revision>
Tested SHA: <full SHA>; integration target/tree: <identifier>
Reviewer context: <distinct from implementing context>
AC-01: PASS - TC-01 - <direct observation/evidence>
AC-02: PASS - TC-02 - <direct observation/evidence>
Tests/checks: <exact commands, inputs, actual results/counts and warnings>
Required checks not run / gaps: none
Effort: <actual minutes if recorded, otherwise unknown>; aggregate effort ledger: <measured value or unknown>
```

For a failing report, start with `QA: FAIL`, retain the identity/revision/check fields, list every criterion's result and add the failed case's steps, expected versus actual output, blocker if any and suggested verification to repeat. Do not include an implementation patch. A user screenshot, green engineer tests or an old PASS alone is not sufficient evidence.

After the latest independent PASS is confirmed against the exact delivered revision, QA or the orchestrator may close the issue. Neither may close after FAIL or while any criterion remains unverified. Earlier retrospective issues stay historical; do not fabricate this report for them or bulk reopen them during workflow installation.
