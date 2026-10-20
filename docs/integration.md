# Frontend / FastAPI integration and acceptance evidence

## Current acceptance status — 2026-10-20

This is an evidence record, not a new QA run. The linked reports below tested application
revision `f421b8432ef93e67e29921663009dd624519bdcb` (tree
`2391d638da6178e9c3abaa938f9e10849f7d64b4`). The current documentation work does not
change application code or the OpenAPI structure; these earlier results are not a fresh
verification of a later delivered tree.

| Issue                                                                                                                              | Tested revision                            | Result and verified scope                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ---------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [#44 — two-real-recipe end-to-end baseline](https://github.com/ttogzhann/freshfirst-market/issues/44#issuecomment-6285195185)      | `f421b8432ef93e67e29921663009dd624519bdcb` | **QA: PASS**, seven criteria. Fresh offline SQLite startup seeded only real TheMealDB IDs `53137` and `52776`, with ten exact normalized lines and shared milk/sugar. The real-source browser/API flow verified whole-batch shopping aggregation, expired-stock exclusion, protected edits, actual-quantity purchase and repeat-safe transfer, atomic cooking, history, restart recovery, and SQLite integrity. Its separate substitution supplement used a clearly labeled synthetic strict test source; it is not production-source evidence. |
| [#45 — offline startup and failed live import](https://github.com/ttogzhann/freshfirst-market/issues/45#issuecomment-6285478790)   | `f421b8432ef93e67e29921663009dd624519bdcb` | **QA: PASS**, four criteria. Normal startup and saved state reopened in separate processes while external sockets were blocked; missing-only seeding preserved newer/non-baseline recipes and empty pantry; a later-page HTTP 503 returned HTTP 502 `SOURCE_UNAVAILABLE` and left the complete stored-state snapshot unchanged.                                                                                                                                                                                                                 |
| [#46 — responsive navigation and critical forms](https://github.com/ttogzhann/freshfirst-market/issues/46#issuecomment-6286106540) | `f421b8432ef93e67e29921663009dd624519bdcb` | **QA: FAIL; issue remains OPEN.** AC-01, AC-02, AC-04 and AC-05 passed. AC-03 substitution persistence was unverified because neither naturally seeded recipe offered an eligible substitution. AC-06 failed: the live import report was clipped/inaccessible at desktop and mobile; closing it also failed to restore focus to its trigger. No PASS exists.                                                                                                                                                                                    |

After that QA report, the owner feasibility note
[on #46](https://github.com/ttogzhann/freshfirst-market/issues/46#issuecomment-6286291524)
records an authorized check of 100 genuine TheMealDB lookup responses. None both passed
the existing strict normalizer and supplied an ingredient eligible under the existing
substitution rules. No records, rules, quantities, files, or acceptance criteria were
changed. This is not a QA PASS and does not resolve either #46 gap.

**#47 final acceptance and closure remain blocked on #46.** Documentation may be prepared
independently, but the open #46 QA FAIL is unresolved. Final acceptance must wait for
current independent PASS evidence on the delivered tree and a check that #44/#45
prerequisite evidence still applies. This page does not claim #47 complete.

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

The authentic brainstorming transcript was not found in the repository or the accessible
session records. The available checkpoint/session summaries and issue records are
summaries, not the original conversation. This scope and evidence note is reconstructed
from the checked-in source records and linked issue reports; it is not a transcript.
No dialogue or undocumented decisions are attributed to that missing conversation.

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
