# FreshFirst task template

PM copies the four sections below into one GitHub issue. Replace placeholders; keep existing FF identity, report context, source decisions and retrospective evidence. Use the [process](process.md), [PM role](team/pm.md) and [testing guidelines](testing-guidelines.md). A template is not a groomed issue until the values are concrete and criteria independently checkable.

## Goal

Describe the user-visible result in one or two sentences and link the relevant specification section. Include GitHub issue number/FF identity and MVP/Post-MVP classification. For a user-discovered bug, retain the original report and the `user-test-bug` label; record steps, expected/actual outcome and affected version/SHA with sanitized inputs.

## Acceptance criteria

- [ ] **AC-01:** Given <specific starting state/input>, when <user/API action>, then <observable result and exact values where applicable>.
- [ ] **AC-02:** Given <invalid/boundary/failure state>, when <action>, then <error/recovery and unchanged data guarantees>.
- [ ] **AC-03:** Given <relevant existing workflow>, when <repeat/reload/restart/concurrent action if applicable>, then <preserved behavior>.

Use as many meaningful criteria as the issue needs; remove irrelevant example cases. Avoid untestable statements such as "works well". Every actual criterion needs QA evidence, not just a checkbox ticked by its author.

### Verification mapping

| Case ID | Criterion | Setup / inputs           | Steps or exact command | Expected observable outcome |
| ------- | --------- | ------------------------ | ---------------------- | --------------------------- |
| TC-01   | AC-01     | <isolated data / source> | <action>               | <specific result>           |
| TC-02   | AC-02     | <failure/boundary>       | <action>               | <specific error and state>  |

For `user-test-bug`, **QA prepares this case plan before implementation**, including the reported reproduction and a regression case that fails on the buggy revision when reproducible. PM acceptance criteria remain the authority; cases must not quietly add scope. A case plan is not a QA PASS. Do not put secrets or production database contents into issue bodies.

## Out of scope

- Name the behavior this issue must preserve and enhancements it must not attempt.
- Link an existing follow-up issue for a deferred requested outcome; if none exists, record it for PM to create only within the authorized scope. Never silently drop a mandatory criterion or invent follow-up issue numbers.
- Do not add authentication, Docker, PostgreSQL, deployment, redesign or guessed quantities/servings to a FreshFirst MVP task.

## Constraints

- **Priority / milestone / labels:** <existing priority, MVP v1.0 or Post-MVP v1.1+, areas; retain `user-test-bug` where applicable>.
- **Dependencies / execution order:** <real issue links and required capability; explicitly state none if independent>.
- **Allowed files / ownership:** <small file set and worktree/branch; identify shared-file conflicts>.
- **Contract / data invariants:** <relevant OpenAPI fields, canonical units, expiry rules, transactions, repeat safety and retained data>.
- **Libraries / environment:** <existing toolchain; uv for Python; avoid unnecessary dependencies or schema changes>.
- **Effort estimate (optional):** <clearly labeled estimate, not a cap>. **Actual effort:** <record only if measured; otherwise unknown>. Do not infer a remaining-time ledger from historical estimates.
- **Acceptance revision / readiness:** <dated revision or comment link, unresolved questions, PM Ready or Blocked>.

### Engineering handoff (issue comment after the work)

Record the exact candidate SHA, branch/worktree, changed files, AC-to-change mapping, tests with commands/results, limitations, relevant QA failure resolved and actual effort only if recorded. Leave the issue open; passing self-tests are a handoff, not independent QA.

### QA and closure record (separate issue comments)

QA uses the [independent verdict format](team/qa-engineer.md#verdict-format), including each criterion, tested SHA, commands/results and reproducible failures. On FAIL, return to engineering and leave the issue open; nobody closes on failure. After an independent PASS, QA may close only after verifying that the tested SHA exactly matches the delivered revision. The orchestrator may close after making the same checks. Record the QA report, acceptance revision and actual effort only when measured. An implementation change after PASS invalidates affected evidence and requires re-verification.
