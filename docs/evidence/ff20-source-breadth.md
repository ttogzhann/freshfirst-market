# FF20 source breadth - 2026-11-01

Acceptance: [FF20-PM-r1](https://github.com/ttogzhann/freshfirst-market/issues/20#issuecomment-6547855239) and [r1a clarification](https://github.com/ttogzhann/freshfirst-market/issues/20#issuecomment-6552473062), preserved in [PM handoff](ff20-pm-2026-11-01.md). Engineering branch `feature/ff20-source-breadth`; starting delivered application `4f39482a994f295c2231527c3223336a2a8569eb`. This document records actual evidence, not independent final QA or issue closure. Effort ledger unknown.

## Reviewed source and exact mappings

Acquired all 26 official first-letter search responses (790 distinct IDs) with TLS verification using the operating-system trust context. The initial default httpx certificate bundle failed local issuer validation; verification was never disabled. Search screening found 24 candidates with existing exact unit grammar and compatible old stock dimensions. Acquired official full lookup responses for the selected additions. Complete raw bytes, exact lookup URLs, UTC times and SHA256 are checked into the [production manifest](../../backend/app/data/mealdb-source/provenance.json) and mirrored in the [review fixture manifest](../../backend/tests/fixtures/mealdb-breadth/provenance.json).

The [independent expectation matrix](../../backend/tests/fixtures/mealdb-breadth/review.json) was transcribed before comparison with the production normalizer. It records all 300 slots: 105 quantified ingredient lines, explicit canonical identities/units/amounts and every blank slot. Duplicate source lines remain: 53409 sugar 300+220=520 g; 53321 dulce de leche 150+150=300 g and coconut flakes 50+50=100 g. Canonical reconciliation yields 102 stored ingredient rows across 15 recipes. Exact factors remain g=1, kg=1000 g, ml=1, l=1000 ml, tsp=5 ml, tbsp=15 ml and explicit counts. No parser or conversion extension.

| External ID | Genuine title                                            | Actual source category |
| ----------- | -------------------------------------------------------- | ---------------------- |
| 53137       | Dulce de Leche                                           | Dessert                |
| 52776       | Chocolate Gateau                                         | Dessert                |
| 53396       | Baghlaw-e-Khanagi                                        | Dessert                |
| 53316       | Beetroot pancakes                                        | Dessert                |
| 53321       | Vanilla alfajores                                        | Dessert                |
| 53452       | Handesh – Bangladeshi rice flour and date molasses cakes | Dessert                |
| 53293       | Pistachio cake                                           | Dessert                |
| 52901       | Rock Cakes                                               | Dessert                |
| 53308       | Rye bread                                                | Side                   |
| 53177       | Spaghetti with Spanish flavours                          | Pork                   |
| 53075       | Tortang Talong                                           | Vegetarian             |
| 53150       | Padron peppers                                           | Vegan                  |
| 53252       | Turkish rice (vermicelli rice)                           | Miscellaneous          |
| 53403       | Muraba-E-Kadu (Pumpkin Jam)                              | Miscellaneous          |
| 53409       | Shendetlie Honey and Nut Cake                            | Dessert                |

Six actual categories, including nine Dessert records. Original two bytes/hashes and ten source quantities are unchanged. Additional valid stored recipes are retained. 53100 was excluded after independent review: blueberry title/instructions conflict with Blackberries/85g slot. Its [unaltered rejected capture](../../backend/tests/fixtures/mealdb-breadth/rejected-53100.json) and provenance/reason remain audit data, never part of the accepted corpus. No missing berry quantity or equivalence was invented.

Added 36 explicit ingredient identities, with all fields recorded in the review matrix. Distinct unsalted/melted butter, ground walnuts, whole/ground cardamom and other source identities remain separate from older stock identities. Only three additive aliases: warm water to existing liquid water; source spelling Ground Cardomom to new ground cardamom; all purpose flour to existing flour. Cornstarch is literal new mass stock with no cornflour alias; egg yolk count remains distinct from whole eggs. The [frozen prior projection](../../backend/tests/fixtures/mealdb-breadth/previous-catalog.json) preserves all 41 original identities, aliases and ten rules/eligibility settings. Existing 40-entry fingerprint remains tested through its old-key projection. No old meaning is redefined.

## Packaging and verification state

Production package validates the exact reviewed-ID set, full raw hashes, lookup provenance, UTC capture timestamps and payload identities. Existing `seed_recipes` normalizes the entire package before its transaction, then adds only missing IDs. Corrupt later entries cannot partially seed earlier records. Newer live recipes, non-corpus recipes, basket references and all user state remain untouched. The existing intentional once-only first-install sample pantry initializer is unchanged; recipe seeding itself never creates/refills user stock.

Focused source/offline/import/persistence checks: 105 passed, one existing Starlette/httpx deprecation warning, 22.02s; Ruff check passed. An earlier focused run had two test-expectation failures (cup rejection wording and old ten-row count), corrected to the existing truthful error text and reviewed 102-row count; no product behavior was changed to satisfy them. Full matrix, actual live import and two-new-record runtime verification were still pending at that earlier engineering checkpoint; completed results follow below. Stage 1 independent review is not final QA.

## Real expanded-corpus HTTP journey and live import

Committed source `5c07123cb4f687f9b9ba752990e6f63f760c66dc`; actual FastAPI on 8002,
Vite at supported origin `http://127.0.0.1:5173`, process-only API URL 8002.
Disposable absolute SQLite file `backend/.qa-state/ff20-engineer-1793501637.sqlite`;
no user database or unknown server touched. Existing first-run sample pantry was
cleared only through this disposable API. Expiry 2026-12-01 remains usable on Nov1.

Used two newly accepted genuine records 52901 Rock Cakes and 53316 Beetroot pancakes.
Checked every expected required amount at 1 and 8 whole batches and persisted/re-read
both selected scales in Basket, then selected 1 each for the stock journey.
Independently combined source demand: self-raising flour 425 g, sugar 75 g, baking
powder 10 ml, butter 150 g, dried fruit 150 g, eggs 4 pcs, milk 65 ml, vanilla 12.5 ml,
beetroot 3 pcs, maple syrup 30 ml, frozen mixed berries 200 g, blackcurrant jam 30 ml,
Greek yogurt 100 g. With existing usable milk 5 ml/butter 10 g, generated shopping
required milk 60 ml/butter 140 g, subtracting each shared stock once; all 13 lines matched.

Purchased checkbox alone changed no stock. Explicit actual-quantity/date confirmation
transferred all 13 lines; repeating a transferred purchase left pantry identical.
Beetroot preview/confirm consumed its exact 11 source lines atomically and created one
history record. Remaining positive stock matched Rock Cakes demand; exhausted entries
were removed by existing behavior. A repeated insufficient beetroot cook returned 409
and left pantry/basket/shopping/history/recipes unchanged.

Terminated owned API PID 29268 and started PID 31176 on the same SQLite file. Complete
API snapshots (recipes, basket choices, shopping/transfer flags, pantry, history)
matched byte-equivalent JSON values before/after browser reload and actual restart.
SQLite integrity ok, foreign-key check empty. Browser Edge observed 15 recipe cards,
all six source categories, existing 1-batch/batch controls, Dashboard recommendations
and expanded history with Beetroot pancakes/neutral Recipe quantity 1 at both actual
1280x800 and 375x812. Request capture proved all frontend API calls used 8002; document
widths equaled viewport widths. Narrow post-restart screenshot was visually reviewed.
Existing frontend was not edited. Harness stopped only its owned API/frontend.

Evidence: `.qa-state/ff20-engineer-runtime.json`, `ff20-engineer-browser-{before,restart}.json`,
matching logs/screenshots and reproducible local harness scripts. Earlier harness
attempts incorrectly expected depleted zero rows and a literal visible Batches label;
corrected only the oracle/selectors to existing row-removal and1batch/accessible
Increase batches behavior. Those incomplete attempts are not accepted passes.

Performed one actual explicit POST live import after the restarted journey:
2026-11-01T02:54:54.050127+00:00 through02:54:59.199259+00:00, HTTP 200,
starting 15 recipes, imported 0, updated 15, total 15, skipped 775. The
[complete actual report](../../backend/tests/fixtures/mealdb-breadth/live-import-2026-11-01.json)
retains every skipped source ID/title/reason. Observed rejection classes: 527 unsupported
identities, 192 unsupported quantities, 56 incompatible dimensions. Counts came from
the real endpoint, not fixture counts; no source failure/fallback was substituted.
For example Apam balik remains skipped for ambiguous Oil, and excluded53100 remains
unsupported rather than changing berry identity. Live import capacity and report/API
semantics were not changed.

## Delivery and remaining independent gate

Only application changes are additive catalog entries/aliases and the reviewed package
ID/provenance validation. Full parsed OpenAPI equals delivered 4f39482 byte-structure
for every field, including all 23 operations. Frontend, backend models/store/schema,
quantity parser and lockfiles are unchanged. Original raw 53137/52776 bytes are identical
to delivered 4f39482, with original SHA256 values retained. Existing frozen tests and new
explicit entry/slot expectations protect old meanings and new additions separately.

A minimal root README paragraph change was additionally authorized because its current
setup still claimed only two offline recipes and uncompleted breadth. It now links this
current implementation/QA status, preserves the original two-record historical minimum
and whole-source-batch semantics. No scope, acceptance or product behavior change.

Independent QA must verify all seven FF20-PM-r1/r1a criteria on the final exact candidate,
including complete source review, network-blocked missing-only restart/no overwrite,
corrupt-package rollback, actual retained UI and source-backed stock journey. Stage1
review and these engineering checks do not close#20. No push, merge, deployment or
GitHub issue edits by engineering. Actual/aggregate effort unknown. HANDOFF.md records
the exact next independent review; deployment preparation remains after verified
functionality, with no paid resources authorized.

## Final engineering command matrix

All eight checks on committed `5c07123cb4f687f9b9ba752990e6f63f760c66dc` returned exit 0.
Backend commands used installed `C:/Users/User/AppData/Roaming/Python/Python312/Scripts/uv.exe`
from `backend/`; frontend commands used existing npm dependencies from `frontend/`.

| Command                                         | Actual result                                                                                   |
| ----------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `uv run --locked pytest -q`                     | 187 passed, 74.67s; one known Starlette/httpx deprecation warning                               |
| `uv run --locked ruff check app tests`          | Passed                                                                                          |
| `uv run --locked ruff format --check app tests` | Passed, 32 files already formatted                                                              |
| `npm test -- --maxWorkers=1`                    | 93 passed in 13 files, 46.50s                                                                   |
| `npm run typecheck`                             | Passed                                                                                          |
| `npm run validate:api`                          | Passed, 23 operations match FreshService                                                        |
| `npm run lint`                                  | Passed, zero errors and six existing Fast Refresh warnings                                      |
| `npm run build`                                 | Passed; existing tsconfig-paths advisory, large-chunk and ignored inlineDynamicImports warnings |

Exact commands, SHA and exits: `.qa-state/ff20-engineer-final-matrix.json`; durable logs
`ff20-engineer-final-{backend-tests,ruff,ruff-format,frontend-tests,typecheck,api,lint,build}.log`.
Earlier committed b214642 passed 187 backend/93 frontend tests but its required formatter
failed one UTC-condition line wrap. Corrected only formatting in 5c07123 and repeated the
complete matrix above; the failed initial log is preserved and is not described as green.
The subsequent evidence/README/HANDOFF commit changes no application behavior; independent
QA must test that exact final revision. No further broad engineering rerun is warranted
solely for evidence prose or the dated live-report artifact.
