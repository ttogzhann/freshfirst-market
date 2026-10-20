# FF-18 source feasibility audit

This audit concerns source evidence for FF-18 only. It does not implement FF-19's startup seed, prove fresh-install/offline behavior, or expand the Post-MVP recipe corpus. GitHub issue [#18](https://github.com/ttogzhann/freshfirst-market/issues/18) remains open until independent QA verifies its current acceptance revision.

## Bounded discovery and acquisition

- Discovery start: **2026-10-20 02:08:21 UTC**. Deadline: 02:38:21 UTC.
- Alphabet acquisition/automated all-line classification completed at **02:09:05.345457 UTC**; final selected lookup capture completed at **02:09:37.788460 UTC**. Source discovery stopped then, after approximately **77 seconds**, well inside the 30-minute gate. Subsequent work is review, tests and handoff, not further discovery.
- A single parallel traversal of `https://www.themealdb.com/api/json/v1/1/search.php?f={letter}`, for `a` through `z`, returned **790 distinct recipe IDs**. All 26 requests succeeded. Each complete record's 20 ingredient/measure slots was checked, rather than stopping at its first invalid line.
- Before any catalog change, **53137 alone passed** the unchanged `normalize_meal`. **789 records failed**, containing **6,601 rejected ingredient lines**. The [complete rejection ledger](ff18-source-rejections.csv) retains every rejected line, source ID/title, raw ingredient/measure and separate identity/quantity reasons. Alphabet-response files remain ignored development artifacts, not a packaged production corpus.
- The initial independent `httpx.get` request using its default certificate bundle failed with `CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`. This is an environment trust-store failure, not a rejected recipe. Retrying with `ssl.create_default_context()` (the production adapter's verified system trust configuration) succeeded. TLS verification was never disabled. No subsequent network failure occurred.
- For an unknown identity, the ledger independently checks whether the measure is parseable in any already supported dimension. A blank quantity-rejection field means its syntax/unit is parseable somewhere; it does **not** invent that identity's canonical dimension or assert the recipe is valid. Known identities are checked against their actual catalog dimension. Unknown names with ambiguous quantities retain both rejection reasons.

## Selected complete, unaltered source responses

Both files contain the complete HTTP JSON response wrapper and all source fields, including empty/null ingredient slots. Neither recipe nor measure text was edited. Capture timestamps, lookup URLs and SHA-256 hashes are recorded in [provenance.json](../../backend/tests/fixtures/mealdb-source/provenance.json).

| ID    | Recipe           | Raw response                                                        | Lookup                                                                         |
| ----- | ---------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| 53137 | Dulce de Leche   | [53137.json](../../backend/tests/fixtures/mealdb-source/53137.json) | [TheMealDB lookup](https://www.themealdb.com/api/json/v1/1/lookup.php?i=53137) |
| 52776 | Chocolate Gateau | [52776.json](../../backend/tests/fixtures/mealdb-source/52776.json) | [TheMealDB lookup](https://www.themealdb.com/api/json/v1/1/lookup.php?i=52776) |

Required source ID, title, category, instructions and image URL are present for both. TheMealDB supplies no verified human yield. `base_servings=1` retains the existing meaning of **one whole source batch**; it does not claim either recipe feeds one person.

## Independent ingredient accounting

These quantities were transcribed and checked from the raw fields before comparison with the normalizer. The exact existing factors are litre = 1,000 ml, tablespoon = 15 ml and teaspoon = 5 ml. Bare egg counts remain counts; no density, piece-to-mass or human-serving conversion is used.

| Source ID / line | Raw ingredient   | Raw measure   | Canonical identity / expected amount                                       |
| ---------------- | ---------------- | ------------- | -------------------------------------------------------------------------- |
| 53137 / 1        | Milk             | 1 Litre       | milk / 1,000 ml                                                            |
| 53137 / 2        | Sugar            | 300g          | sugar / 300 g                                                              |
| 53137 / 3        | Baking Powder    | 1/4 tsp       | baking_powder / 1.25 ml                                                    |
| 53137 / 4        | Vanilla Extract  | 1 teaspoon    | vanilla / 5 ml                                                             |
| 52776 / 1        | Plain chocolate  | 250g          | Requires dedicated plain_chocolate / 250 g; initially unsupported identity |
| 52776 / 2        | Butter           | 175g          | butter / 175 g                                                             |
| 52776 / 3        | Milk             | 2 tablespoons | milk / 30 ml                                                               |
| 52776 / 4        | Eggs             | 5             | egg / 5 pcs                                                                |
| 52776 / 5        | Granulated Sugar | 175g          | sugar / 175 g                                                              |
| 52776 / 6        | Flour            | 125g          | flour / 125 g                                                              |

All other source slots (53137: 5–20; 52776: 7–20) contain empty/null ingredient names and only empty/whitespace/null measures. No nonblank line is discarded. Neither record repeats a canonical ingredient internally, so per-recipe normalized totals equal the table. Shared canonical stock is **milk and sugar**; at one batch each, combined demand would be 1,030 ml milk and 475 g sugar. Existing duplicate-line aggregation coverage is retained in `tests/test_importer.py`.

The source's Dulce de Leche ingredient field says “Baking Powder” while its instruction prose says “baking soda”. Both remain unaltered. This audit maps the explicit structured ingredient field as the existing importer does; it does not silently substitute an ingredient or rewrite the source's cooking instructions.

## Feasibility decision and verification

At the initial catalog boundary the gate was blocked: no second valid record existed. Chocolate Gateau is the smallest concrete candidate: exactly one missing identity, with an explicit 250 g amount and all other lines fully supported. Plain chocolate cannot be mapped to cocoa powder or unspecified chocolate without changing identity.

[PM revision FF18-PM-r2](https://github.com/ttogzhann/freshfirst-market/issues/18#issuecomment-6281712648) explicitly authorized one additive `plain_chocolate` identity, display name Plain chocolate, category Pantry staples, canonical unit g. It is not an alias for cocoa or generic chocolate. The original forty identities, aliases and substitution rules remain unchanged. No quantity, serving, schema or production bootstrap logic changes. With this single reviewed identity, **both captured records pass the unchanged strict normalizer**, sharing milk and sugar. The rejection ledger deliberately retains the initial forty-identity audit so the original blocker and reasoning remain visible; it does not describe the final supported catalog as still having forty entries.

Focused deterministic coverage is in [test_real_recipe_baseline.py](../../backend/tests/test_real_recipe_baseline.py). It verifies source hashes/provenance, all source slots, explicitly transcribed quantities/units, distinct IDs/shared stock and whole-batch semantics, plus rejection of ambiguous, volume and count measures for a mass ingredient. A frozen baseline fingerprint also checks the exact original forty catalog records, aliases and all substitution rules/category constraints. The existing persistence test's catalog count becomes 41; repeat-safe seeding expectations remain. Tests do not access the live network. Final PM revision, candidate and executed check results belong in the issue handoff; this document alone is not QA PASS.
