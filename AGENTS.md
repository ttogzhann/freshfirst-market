<!-- LOVABLE:BEGIN -->

> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.

<!-- LOVABLE:END -->

## Development workflow

- Use uv for Python backend dependencies and the tracked npm lockfile for frontend dependencies.
- Commit changes regularly to Git. Preserve published history and the existing working application.
- Read [the product specification](docs/spec.md) and [the approved issue plan](docs/issues-plan.md). GitHub Issues are the active task tracker; the plan preserves scope, FF identifiers and history.
- Before authorized issue work, follow [the development process](docs/process.md). The main session orchestrates separate PM, Software Engineer and independent QA contexts; it does not replace those roles with its own verdict.
- PM grooms one issue using [the task template](docs/task-template.md) and [PM instructions](docs/team/pm.md).
- The [Software Engineer](docs/team/software-engineer.md) implements and tests one groomed issue, commits a candidate and leaves the issue open.
- [QA](docs/team/qa-engineer.md) independently verifies every acceptance criterion. QA FAIL returns to the engineer; QA does not repair the code or close on failure. QA may close only after an independent PASS and confirmation that the passed SHA exactly matches the delivered revision; the orchestrator may close after making the same checks.
- For user-discovered bugs, retain `user-test-bug` and require PM grooming, QA test cases before implementation, engineering regression/fix and independent QA verification.
- Before writing/running tests, read [testing guidelines](docs/testing-guidelines.md). Preserve all 23 operations in [OpenAPI](openapi.yaml), SQLite integrity, exact units, expiry rules and the existing frontend design.
- The 12-hour figure is only a historical internal planning target, not a mandatory cap, stop condition or acceptance gate. Record estimates as estimates and report actual effort only when it was tracked; otherwise state that the effort ledger is unknown. Never bypass verification or move a core bug to Post-MVP to satisfy a time target.
- These process documents apply prospectively. Do not claim earlier implementation or retrospective closures used this workflow. Do not reopen them merely to install it.
- Reading/installing these instructions does not authorize starting a remaining issue, launching a loop, pushing code or deploying. Follow the user's current task scope; do not start the backlog during workflow setup.

## Common checks

Backend, from `backend/`: `uv run --locked pytest -q`, `uv run --locked ruff check app tests`, `uv run --locked ruff format --check app tests`.

Frontend, from `frontend/`: `npm test`, `npm run typecheck`, `npm run validate:api`, `npm run lint`, `npm run build`.

For documentation-only changes, use the local-link, workflow-structure, formatting and configuration checks in the testing guidelines. No process automation or CI enforcement is installed by the Markdown files themselves.
