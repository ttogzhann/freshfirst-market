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

Focused source/offline/import/persistence checks: 105 passed, one existing Starlette/httpx deprecation warning, 22.02s; Ruff check passed. An earlier focused run had two test-expectation failures (cup rejection wording and old ten-row count), corrected to the existing truthful error text and reviewed 102-row count; no product behavior was changed to satisfy them. Full matrix, actual live import and two-new-record runtime verification are still pending at this engineering checkpoint. Stage 1 independent review is not final QA.
