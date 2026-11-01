# Frontend / FastAPI integration and acceptance evidence

## Source-breadth engineering refresh — 2026-11-01

The [FF20 source-breadth record](evidence/ff20-source-breadth.md) documents 15 reviewed
genuine recipes across six actual categories, preserving both original captures,
all 41 old ingredient meanings and ten substitution rules. Existing whole-batch,
SQLite, 23-operation contract and accepted Dashboard/full-history UI remain unchanged.
The newly reviewed source matrix accounts for all 300 slots/105 quantified lines.

Engineering exercised two new genuine recipes through 1/8 scaling, shared-stock
shopping, explicit purchase/repeat transfer, exact cook/history, insufficient-stock
rollback and actual same-file process restart. Real browser discovery showed 15 cards,
six categories and retained history at both required viewports. One actual live import
on 2026-11-01 returned HTTP 200: starting 15, imported 0, updated 15, total 15, skipped 775;
the complete report and precise times are linked from the evidence record.

This is engineering evidence, not final independent QA or delivered issue closure.
Earlier two-record results below remain historical checkpoints. Final exact-SHA
independent source/behavior/regression verification remains required before #20 closes.

## Engineering integration refresh — 2026-10-31

The [final engineering record](evidence/final-acceptance.md#engineering-integration-refresh--2026-10-31-ff48-pm-r1)
records all eight required checks passing on `f0f2820d686be59408b970cac6b066d48b9884ba`:
153 backend tests, 89 frontend tests, Ruff/format, typecheck, 23-operation validation,
lint and build. It also records a genuine two-recipe HTTP purchase/cook journey,
exact shared-stock aggregation, browser page reloads and an actual backend restart
reopening the same disposable SQLite file with identical persisted state and
repeat-safe transfer. Existing warnings and the corrected disposable harness
assumption are disclosed there. No source or dependency changes were required.

[#47 independent PASS](https://github.com/ttogzhann/freshfirst-market/issues/47#issuecomment-6340220649)
covered all eight documentation criteria on that SHA. The earlier #46 PASS remains
linked below. Fresh independent final-matrix/runtime/UI verification and exact
SHA/delivery checks are still required; this engineering refresh does not close
#46/#47/#48 or claim independent QA success for a later evidence commit.

## Independent acceptance checkpoint — 2026-10-22

[#46 independent QA](https://github.com/ttogzhann/freshfirst-market/issues/46#issuecomment-6340133326)
now reports **PASS for all seven FF46-PM-r3 criteria** on
`0147990ac179dd7dd1817ef250554ee7b4bc7f04` (tree
`0630c6c07aa1d8b5591238ec3c92a0c0d5675dee`). Windows x64, Edge
155.0.4283.62, supported origin 127.0.0.1:5173/API 8000 and disposable file-backed
SQLite were used. At actual 1280x800 and 375x812, QA verified keyboard navigation,
pantry validation/error/retry/edit/refresh, genuine-source batch scaling and saved
scale, shopping overwrite/purchase confirmation, atomic cooking and stale-stock
recovery, and the natural 788-entry report through its final entry with both close
paths returning focus. Substitution coverage remains separately labeled test-only
fixture coverage, not a real-source substitution journey. Independent focused checks
passed 30 backend and 24 frontend tests; the known Starlette/httpx deprecation warning
remained. Full suites/build are not claimed by this report.

Earlier incomplete keyboard/viewport evidence is preserved in the
[2026-10-20 QA FAIL](https://github.com/ttogzhann/freshfirst-market/issues/46#issuecomment-6287820172),
which tested application `9c528acfeb3100136b754f3ab482c6336b48b3d2` with evidence
revision `899dccd`. It reported verification gaps rather than a newly confirmed bug.
The fresh report supersedes those gaps for its exact tested revision; it does not
rewrite earlier FAIL records or itself prove delivery or closure.

**#47 awaits independent documentation QA and delivered-tree prerequisite review.**
The #46 independent verification blocker now has a PASS, while exact delivery-SHA
validation and #44/#45 evidence applicability remain required before final acceptance.
This documentation reconciliation changes no application code. It does not claim
#46/#47 closed, final MVP acceptance, or a new #44/#45 browser run.

### Historical acceptance checkpoint — 2026-10-20

This is an evidence record, not a new QA run. The linked reports below tested application
revision `f421b8432ef93e67e29921663009dd624519bdcb` (tree
`2391d638da6178e9c3abaa938f9e10849f7d64b4`). The current documentation work does not
change application code or the OpenAPI structure; these earlier results are not a fresh
verification of a later delivered tree.

| Issue                                                                                                                              | Tested revision                            | Result and verified scope                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ---------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [#44 — two-real-recipe end-to-end baseline](https://github.com/ttogzhann/freshfirst-market/issues/44#issuecomment-6285195185)      | `f421b8432ef93e67e29921663009dd624519bdcb` | **QA: PASS**, seven criteria. Fresh offline SQLite startup seeded only real TheMealDB IDs `53137` and `52776`, with ten exact normalized lines and shared milk/sugar. The real-source browser/API flow verified whole-batch shopping aggregation, expired-stock exclusion, protected edits, actual-quantity purchase and repeat-safe transfer, atomic cooking, history, restart recovery, and SQLite integrity. Its separate substitution supplement used a clearly labeled synthetic strict test source; it is not production-source evidence. |
| [#45 — offline startup and failed live import](https://github.com/ttogzhann/freshfirst-market/issues/45#issuecomment-6285478790)   | `f421b8432ef93e67e29921663009dd624519bdcb` | **QA: PASS**, four criteria. Normal startup and saved state reopened in separate processes while external sockets were blocked; missing-only seeding preserved newer/non-baseline recipes and empty pantry; a later-page HTTP 503 returned HTTP 502 `SOURCE_UNAVAILABLE` and left the complete stored-state snapshot unchanged.                                                                                                                                                                                                                 |
| [#46 — responsive navigation and critical forms](https://github.com/ttogzhann/freshfirst-market/issues/46#issuecomment-6286106540) | `f421b8432ef93e67e29921663009dd624519bdcb` | **QA: FAIL at this checkpoint; issue was OPEN.** AC-01, AC-02, AC-04 and AC-05 passed. AC-03 substitution persistence was unverified because neither naturally seeded recipe offered an eligible substitution. AC-06 failed: the live import report was clipped/inaccessible at desktop and mobile; closing it also failed to restore focus to its trigger. No PASS existed at this checkpoint.                                                                                                                                                 |

After that QA report, the owner feasibility note
[on #46](https://github.com/ttogzhann/freshfirst-market/issues/46#issuecomment-6286291524)
records an authorized check of 100 genuine TheMealDB lookup responses. None both passed
the existing strict normalizer and supplied an ingredient eligible under the existing
substitution rules. No records, rules, quantities, files, or acceptance criteria were
changed. This was not a QA PASS and did not resolve either #46 gap at that checkpoint.

At that checkpoint, **#47 final acceptance and closure were blocked on #46**.
Documentation could be prepared independently, while #46 QA FAIL remained unresolved.
The current dated status above records subsequent evidence; delivered-tree checks and
independent documentation QA still apply.

### Source record and batch meaning

The checked-in provenance record is
[`backend/app/data/mealdb-source/provenance.json`](../backend/app/data/mealdb-source/provenance.json).
It links the source lookup URLs, capture times, and SHA-256 values for the unaltered
[`53137.json`](../backend/app/data/mealdb-source/53137.json) and
[`52776.json`](../backend/app/data/mealdb-source/52776.json) payloads. The corresponding
FF-18 capture files are under
[`backend/tests/fixtures/mealdb-source/`](../backend/tests/fixtures/mealdb-source/).
The #44 report records matching raw-byte hashes:

- `53137`: `2d032ad24e25a2ca8137a3019fd7a6878e8835214ceff9dbdf61255488fd402c`
- `52776`: `718fa6ad455236d5a81de755ca4190725025e510041182e55f68a1124a049814`

Both recipes are real source records, with ten validated ingredient lines in total.
For these imported recipes `base_servings=1` is one complete source-recipe batch, not a
person or serving count. The 15–20 recipe breadth was an internal planning target and
optional FF-20 expansion; it is not a university requirement and is not claimed complete.

At the earlier 2026-10-20 documentation checkpoint, the authentic brainstorming transcript
had not been available in the repository or accessible session records. The scope and
evidence note above was reconstructed from checked-in records and linked issue reports;
it was not a transcript. Later on 2026-10-20 the owner supplied a partial original excerpt,
now preserved in [brainstorming history](brainstorming.md). Repetitions and gaps remain
as supplied; no missing dialogue or undocumented decisions have been invented. This
historical record does not change the open acceptance gates or claim final QA PASS.

## Historical integration evidence

The entries below preserve earlier results for context. They describe the revisions and
test setup that were actually recorded at the time; they are not fresh checks of this
documentation candidate.

### Earlier SQLite persistence verification — 2026-10-20

The prior integration record reported 99 backend tests and 47 frontend tests. It also
recorded a separate-process reopen of a file-backed SQLite database, retaining pantry
(including expired entries), imported recipes, basket/substitutions, generated/edited/
manual shopping rows, transfer flags, cooking history and removed-generated-line edit
protection. Injected SQL write failures rolled back inventory and history/transfer
completion. Six independent engines serialized competing cooks and transfers. Repeated
import retained basket references; the catalog/rule counts in that historical snapshot
were 40/10 (the current catalog count is documented in the backend README), and deleting
pantry entries did not reseed inventory. The frontend run exercised all 23 operations through
the production HTTP adapter against SQLite.

That record noted existing Fast Refresh, build, and deprecation warnings, and explicitly
said it did not perform a new live-source audit or browser walkthrough. Its stored test
counts are historical results, not evidence that #46 passed.

### Previous HTTP integration and browser walkthrough — in-memory phase (historical)

The earlier HTTP/browser record used the real HTTP adapter and FastAPI, but its
integration source was a synthetic, exactly quantified test recipe. The browser flow
covered pantry CRUD, recipe detail, scaling/substitution, basket, shopping, purchase,
cooking, conflicts and API outage recovery. It recorded 91 backend tests, 47 frontend
tests, TypeScript/API validation/build/Ruff checks, and six existing React Fast Refresh
warnings plus build/plugin and Starlette/httpx deprecation warnings.

In that phase, restarting FastAPI reset state because the backend used an in-memory
store. For example, after restart the browser recovered to the empty pantry expected
from that store. This is a historical observation only: the current backend uses
SQLAlchemy/SQLite and the #44/#45 reports above independently checked persistence and
offline recovery. Existing browser localStorage mock data is not migrated, and
production requests do not silently fall back to mock data after an API failure.

## Setup and verification entry points

- Integrated local startup and environment configuration: [`README.md`](../README.md).
- Backend SQLite URL, seed and import details: [`backend/README.md`](../backend/README.md).
- API structure: [`openapi.yaml`](../openapi.yaml) (23 unauthenticated operations).
- Relevant offline baseline and persistence tests are listed in the backend README and
  [`testing guidelines`](testing-guidelines.md).

The packaged baseline lets a fresh install seed missing reviewed IDs offline. The
Recipes import action is a separate live-source request and requires network access; a
failed import reports its source error and preserves saved data. No live import is
performed by this documentation record.

## Handover decision discussion — 2026-10-20

This is a contemporaneous record of the current handover discussion, not a reconstructed
transcript of earlier brainstorming. The owner explicitly required preserving existing
work, finishing #46–#48, independent QA and removing the internal 12-hour blocking rule.
The orchestrator selected a clean worktree from verified main and the engineer integrated
existing candidates instead of rebuilding the application. PM separately reviewed the
remaining acceptance criteria. Engineering retained strict recipe normalization and used
the preserved import-report fix and documentation candidates without expanding scope.

During execution, occupied application ports required an isolated 8001/5174 runtime.
The existing CORS policy permits 5173; the resulting browser limitation was reported to QA
instead of weakening application security for a test. Windows CRLF checkout caused lint
format errors; LF normalization in this clean worktree produced no committed source diff.
A frontend test exceeded its five-second timeout under concurrent load; rerunning the full
suite with one worker passed all 89 tests. These are actual observed decisions and results.
