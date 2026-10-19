# FreshFirst MVP v1.0 - 12-hour delivery backlog

Planning revision, 2026-10-20. Application reviewed: `b54a99a4cd4b647fdca6c1f2f7b72570a2e4a94e`. Earlier 48-issue plans are preserved at `9a89f63` and `18d4955`. This revision implements the user's request to change the specification boundary, not application behavior. FF identifiers are local references; no GitHub issues/milestones or implementation worktrees have been created.

## Operative boundary and counts

**48 meaningful issues: 33 MVP Completed, 13 MVP Remaining, 2 Post-MVP.** Existing working features and all 23 API operations remain intact. No critical bug or data-integrity requirement is deferred. The explicit scope changes are in `docs/spec.md` section 9 and the change log below; the former assertion that every original item remained mandatory is historical, not the operative boundary.

Smallest complete MVP: pantry CRUD/search/filters and expiry-aware stock; at least **two distinct fully quantified real TheMealDB recipes with a shared ingredient**; recipe search/ranking/details; honest whole-recipe batch scaling 1-8; reviewed explicitly confirmed substitutions; persistent unique basket; shared shopping aggregation, manual edits and overwrite confirmation; actual-quantity/date purchase transfer exactly once; revalidated atomic cooking/history; recent-history Dashboard; SQLite restart/offline recovery; basic responsive usable forms and truthful errors.

The real production seed must not be synthetic. Two records is a revised minimum, not evidence that a second valid record currently exists. The historical audit accepted one. A one-recipe demo does not close the revised MVP. No normalization rule, quantity, yield or safety invariant may be invented to meet the deadline.

| Milestone | Issue range | MVP Completed | MVP Remaining | Post-MVP |
| --- | --- | ---: | ---: | ---: |
| M0 - Specification and architecture | FF-01 to FF-05 | 5 | 0 | 0 |
| M1 - Pantry and application shell | FF-06 to FF-11 | 6 | 0 | 0 |
| M2 - Source baseline and recipe discovery | FF-12 to FF-21 | 6 | 3 | 1 |
| M3 - Basket, shopping and cooking | FF-22 to FF-31 | 10 | 0 | 0 |
| M4 - Persistence and integration | FF-32 to FF-37 | 6 | 0 | 0 |
| M5 - Completion and focused acceptance | FF-38 to FF-48 | 0 | 10 | 1 |
| Total | 48 | 33 | 13 | 2 |

### Classification and priority

- **MVP Completed:** implemented at the recorded application commit with preserved evidence. Zero remaining implementation effort; keep these features/tests. A separate remaining issue can still correct a specific gap.
- **MVP Remaining:** mandatory correctness, baseline data, configuration, UX or acceptance evidence under the revised spec. Ready/blocked describes prerequisites, not a weaker requirement.
- **Post-MVP:** optional breadth/depth beyond the revised complete journey. Only FF-20 (expand to 15-20 strict real recipes with corpus coverage) and FF-43 (browse all older history in UI) qualify. Neither is implemented or silently accepted.
- **P0:** data integrity or release-blocking MVP acceptance. **P1:** remaining required configuration/UX/evidence. **P2:** genuine v1.1+ enhancement; no P2 issue is a release dependency.
- Budgets below are small task timeboxes for the reduced solution, not evidence of completed fixes. Stop and escalate on an overrun; do not keep expanding scope. Completed dependencies are satisfied; keep transitive prerequisites.

### Scope preservation

Do not remove existing filters, import capacity, valid stored recipes, catalog/rules, backend expiry configurability, basket/shopping features, full history API or SQLite safeguards. Retain default three-day expiry plus coordinated existing configuration. No redesign or new API/schema, auth, Docker, PostgreSQL, deployment, CI/CD project, unrestricted import, analytics or extra integrations. Whole-batch labels correct a promise; they do not guess human portions. Full older history stays stored and available through the existing API even when its extra UI is Post-MVP.

## Smallest reliable TheMealDB solution

1. Timebox FF-18 to **30 minutes**: inspect raw current/captured source responses for two distinct recipes that the strict normalizer can fully quantify with the existing catalog and shared stock. Existing fixture ID `53137` is accepted; the other captured record is not a second accepted recipe. Do not claim feasibility before checking every line.
2. FF-19 may use narrowly proven identity aliases, but no guessed density, count-to-mass, cups, packages, missing amounts, omitted ingredients or yield conversion. If canonical-unit changes or a broad catalog expansion would be required, stop rather than hiding a migration under the deadline.
3. Package only the two reviewed **unaltered raw TheMealDB responses**, with source ID/URL/capture date. Reuse the existing `MealSource`/`normalize_meal` and external-ID transaction path to seed missing records. Do not copy synthetic HTTP-test recipes or hand-author normalized production recipes. Add focused raw-to-expected-quantity, rejection, repeated-seed and offline tests in FF-19/FF-21; these tests do not wait for Post-MVP FF-20.
4. Never replace a newer stored source record with an older baseline snapshot; seed only missing IDs. No duplicate ingredients, recipes, choices or user pantry additions. An initialized database must not wait for a whole-alphabet network traversal to become usable. Live explicit import remains available, retains existing reports/errors and cannot replace failed network calls with fake success. Preserve imported data on failure.
5. Use **one complete source batch** as the exact baseline (`base_servings=1`); UI explicitly labels selected batches 1-8. API field names and arithmetic remain unchanged. No human serving yield needs to be researched or guessed for this boundary.

Fresh local installation can seed the reviewed source snapshots offline; obtaining/provenance-checking the snapshots requires real connectivity during preparation. This is a deliberate initial-connectivity change, not a claim that handwritten data is TheMealDB data. The live API's response contract is unchanged. If two qualifying records cannot be found in the timebox, report the blocker and remaining alternatives before spending reserve. Do not substitute a broken core or a fictional recipe. Neither a second valid source record nor this bootstrap is implemented by these documentation edits.

## Review evidence and boundaries

Read `AGENTS.md`, `docs/spec.md`, `openapi.yaml`, `docs/integration.md`, READMEs, backend routers/models/services/catalog/importer/quantity logic/SQLite adapter, frontend service implementations/hooks/product routes/components and tests. Reviewed Git history including file history across the frontend move. Do not rewrite published history.

| Commit | Contribution supported by its diff |
| --- | --- |
| `13508ba` | Aligned specification and repository workflow |
| `16ec563` | Moved the existing frontend into `frontend/`; not the original implementation of all UI |
| `5153960` | Introduced authored OpenAPI from frontend calls |
| `a053f16` | Completed basket/shopping frontend and strengthened mock/domain/contract tests |
| `1bf7f6e` | Added modular FastAPI, strict TheMealDB adapter and backend tests |
| `a507929` | Connected HTTP service, CORS, real HTTP tests and recorded browser integration |
| `b54a99a` | Added SQLAlchemy/SQLite and durable rollback, restart and independent-connection tests |

Preserved verification from the original backlog review at application commit `b54a99a` (recorded in `9a89f63`); no application tests were rerun for this scope-planning-only edit:

- Backend `uv run --locked pytest -q`: **99 passed**. Ruff check/format check passed for 25 Python files. Existing Starlette TestClient/httpx deprecation warning remains.
- Frontend `npm test`: **47 passed in six files**. Typecheck and API validation passed; validation reports **23 operations** with no authentication.
- ESLint and production build passed in the preceding storage verification at the same application commit; not rerun for this documentation-only review. Existing six Fast Refresh warnings/build notices are not new blockers.
- `docs/integration.md` records an earlier browser walkthrough using a synthetic strictly quantified recipe before SQLite, plus separate automated SQLite verification. It does not claim a combined real-source browser/backend-restart acceptance run.
- `backend/README.md` records a historical live audit: **790 fetched, one accepted**. This is not a live count rechecked today. Two real raw fixtures do not prove 15 supported recipes.
- Mock tests accepting 15-20 bundled records and synthetic backend tests accepting 20 establish mechanics only, not production source sufficiency.

No live TheMealDB fetch was made during the original planning or this scope revision. Proposed live audit and source-dependent work remain open. Python commands below run from `backend/`; npm commands from `frontend/`. Completed-issue testing steps explain reproduction, not additional backlog tasks.


## M0 - Specification and architecture

### FF-01 - Establish v1.0 scope and the acceptance matrix

**MVP Completed | P1 | Dependencies: none**

MVP scope basis: Sections 1-2 and 7-8: scope, workflow and explicit acceptance matrix.

Description: Define local single-user journeys, canonical quantities, phased workflow and non-goals.

Acceptance criteria: Specification covers pantry, import, substitutions, basket, shopping, cooking/history and dashboard; expiry and ambiguity restrictions are explicit; no additional product scope is implied.

Testing steps: Compare `docs/spec.md` sections 1-8 with the API and coverage matrix below. Check unresolved count/yield questions are not accepted silently.

Evidence: `13508ba`; `docs/spec.md`, `AGENTS.md`. The historical 12-hour aspiration is not a remaining-work guarantee.

### FF-02 - Organize reproducible frontend and backend environments

**MVP Completed | P1 | Dependencies: FF-01**

MVP scope basis: Section 2: repository layout, uv/npm setup and reproducible local workflow.

Description: Separate project directories and establish tracked npm/uv lockfile workflows.

Acceptance criteria: Frontend and backend have their documented locations; one documented lockfile/install procedure exists for each; startup and verification commands are supplied.

Testing steps: Reproduce `uv sync --locked` and tests; run `npm ci`, typecheck and build in a disposable checkout. Do not change dependencies merely to clear notices.

Evidence: `16ec563`, `a053f16`, `1bf7f6e`; READMEs, `frontend/package-lock.json`, `backend/uv.lock`. The original backlog verification used installed dependencies, not a fresh npm reinstall; no install was repeated for classification.

### FF-03 - Provide one typed frontend service boundary and injectable mock

**MVP Completed | P1 | Dependencies: FF-01**

MVP scope basis: Sections 1-2: centralized frontend service interface and tested mock phase.

Description: Centralize calls behind `FreshService` for transport-independent UI and isolated tests.

Acceptance criteria: Screens call through the service/hooks layer; mock and HTTP implementations share types; tests can inject a service; production never silently substitutes mock success after API failure.

Testing steps: Run frontend mock/domain tests; inspect `services/types.ts`, `index.ts` and production selection.

Evidence: Existing frontend retained by `16ec563`, refined by `a053f16` and `a507929`; mock suite passes. Mock recipe counts do not establish the live corpus.

### FF-04 - Author and validate all 23 public OpenAPI operations

**MVP Completed | P0 | Dependencies: FF-03**

MVP scope basis: Sections 2 and 6: authored OpenAPI operations, schemas and errors.

Description: Define methods, models, statuses, query encoding and errors without authentication.

Acceptance criteria: Exactly 23 operations match `FreshService`; field names/arrays match callers; validation/conflict errors follow the standard envelope.

Testing steps: Run `npm run validate:api` and `uv run pytest -q tests/test_contract.py`; compare registered routes as well as the served authored document.

Evidence: `5153960`, `a053f16`, `1bf7f6e`; OpenAPI 3.0.3 and actual response-schema validation. Stale descriptive prose is FF-47.

### FF-05 - Implement modular FastAPI routing and shared error handling

**MVP Completed | P1 | Dependencies: FF-04**

MVP scope basis: Sections 2, 4 and 6: modular FastAPI implementation and consistent API validation.

Description: Route catalog, pantry, basket, shopping and cooking into domain services with consistent validation/errors.

Acceptance criteria: Operations exist under `/api`; missing resources, invalid inputs and conflicts return documented statuses/envelopes; unexpected failures never report success.

Testing steps: Run `tests/test_contract.py` and `tests/test_validation.py`; exercise malformed queries, absent resources and null/invalid patches.

Evidence: `1bf7f6e`; `app/main.py`, routers, `models.py`, `errors.py`; current backend suite passes.

## M1 - Pantry and application shell

### FF-06 - Define the supported canonical ingredient catalog

**MVP Completed | P1 | Dependencies: FF-01, FF-05**

MVP scope basis: Sections 3.1, 3.2 and 5: predefined supported identities and canonical units.

Description: Provide a small stable catalog with category, identity and canonical stock dimension.

Acceptance criteria: Forty identities have stable IDs and g/ml/pcs units; API lists them; only explicit aliases map upstream names to supported identities.

Testing steps: List ingredients; inspect `app/catalog.py`; run importer identity cases and persistence seed-count assertions.

Evidence: `1bf7f6e`, `b54a99a`; catalog/schema tests. The two-recipe baseline remains FF-18/FF-19; 15-20 recipe breadth is Post-MVP FF-20.

### FF-07 - Implement pantry CRUD and one entry per ingredient

**MVP Completed | P0 | Dependencies: FF-06**

MVP scope basis: Section 3.1 and acceptance criteria 1-2: pantry CRUD and one expiry batch per ingredient.

Description: Create, replace and delete pantry stock, merging compatible quantities only at the same expiry.

Acceptance criteria: Equal-expiry additions combine; different expiry conflicts without mutation; edits cannot duplicate another ingredient; expired entries stay editable/removable.

Testing steps: Run pantry validation/contract tests; add 0.1 kg plus 100 g with equal dates, then conflicting dates, and compare quantities.

Evidence: `1bf7f6e`; pantry router, `merge_pantry`, validation tests; database uniqueness in `b54a99a`.

### FF-08 - Validate quantities, calendar dates and compatible units

**MVP Completed | P0 | Dependencies: FF-05, FF-06**

MVP scope basis: Sections 3.1-3.2 and 4: positive canonical quantities, valid dates and compatible units.

Description: Normalize only supported dimensions with decimal arithmetic and reject invalid inventory inputs.

Acceptance criteria: Quantities are positive and finite; real calendar dates are required; g/kg and ml/l/kitchen-volume table normalize; dimensions never cross implicitly; tiny nonzero requirements cannot round into free ingredients.

Testing steps: Run validation/quantity tests, including booleans, NaN/infinity, zero, incompatible units, impossible dates and tiny amounts.

Evidence: `1bf7f6e`; models and `services/quantities.py`. This does not authorize additional guessed conversions.

### FF-09 - Exclude expired stock from calculations and handle expiry urgency

**MVP Completed | P0 | Dependencies: FF-07, FF-08**

MVP scope basis: Sections 3.1-3.2 and acceptance criteria 2-3: expired-stock exclusion and urgency.

Description: Keep expired stock visible but unusable and rank eligible near-expiry ingredients appropriately.

Acceptance criteria: Matching, substitutions, shopping and cooking use zero expired stock; today through day three is inclusive by default; urgency is not a food-safety guarantee.

Testing steps: Run `test_calculations.py` and inventory tests with yesterday/today/day-three/day-four dates; compare every availability calculation.

Evidence: `1bf7f6e`, `b54a99a`; `stock`, `summary`, dashboard tests. Non-default threshold presentation remains FF-39.

### FF-10 - Deliver pantry cards, search, filters and edit forms

**MVP Completed | P1 | Dependencies: FF-03, FF-07, FF-08, FF-09**

MVP scope basis: Section 3.1 and section 4: pantry browsing/filtering, forms and basic states.

Description: Browse and manage pantry inventory through the established frontend.

Acceptance criteria: Ingredient search, category/expiry filters, quantities/dates, compatible-unit forms and CRUD controls exist; loading/empty/error states are present.

Testing steps: Run domain/routing/HTTP integration tests; reproduce recorded browser CRUD; inspect filter predicates in `routes/pantry.tsx`.

Evidence: `a053f16`, `a507929`, `docs/integration.md`. Filters are code-reviewed; comprehensive pantry component automation is not claimed. Inline server feedback remains FF-42.

### FF-11 - Deliver desktop navigation and responsive application shell

**MVP Completed | P1 | Dependencies: FF-01, FF-03**

MVP scope basis: Sections 1 and 4: five destinations, desktop sidebar and responsive collapse.

Description: Expose Dashboard, Pantry, Recipes, Basket and Shopping List with sidebar and compact-screen menu.

Acceptance criteria: All destinations resolve; responsive toggle/menu-close behavior is implemented; existing visual identity remains intact.

Testing steps: Run `src/test/app-routing.test.tsx`; inspect `AppShell.tsx` responsive classes and reproduce documented desktop navigation.

Evidence: Existing frontend retained in `16ec563`, navigation completed in `a053f16`. Narrow-screen/keyboard acceptance is still FF-46; routing tests do not prove mobile interaction.

## M2 - Source baseline and recipe discovery

### FF-12 - Fetch real TheMealDB candidates through the backend

**MVP Completed | P1 | Dependencies: FF-05**

MVP scope basis: Section 3.2: real backend TheMealDB discovery and source error handling.

Description: Traverse first-letter searches per import, deduplicate IDs and handle upstream failures.

Acceptance criteria: Response shape is validated; timeouts and TLS verification are enabled; failures become `SOURCE_UNAVAILABLE`; page reads do not import.

Testing steps: Run source-adapter/failure tests in `test_importer.py`; verify mocked letter traversal, malformed payload rejection and deduplication; inspect timeout/TLS setup.

Evidence: `1bf7f6e`; `TheMealDBSource`. Adapter mechanics are separate from source sufficiency in FF-18 to FF-21.

### FF-13 - Reject unquantified recipes and normalize exact supported measures

**MVP Completed | P0 | Dependencies: FF-06, FF-08, FF-12**

MVP scope basis: Section 3.2 and acceptance criterion 5: quantified supported recipes with no guessed measures.

Description: Accept only supported identities and confidently quantified lines with complete metadata.

Acceptance criteria: Exact fractions work; repeated identities aggregate; unsupported names, ranges, undefined cups, packages, pinches and to-taste measures are rejected with reasons; no ingredient line silently disappears.

Testing steps: Run exact/ambiguous quantity and captured-source cases in `test_importer.py`; compare normalized output with raw fixture lines.

Evidence: `1bf7f6e`; `normalize_meal`, `parse_measure`, two real captured responses. This does not prove 15 accepted real recipes.

### FF-14 - Upsert source recipes idempotently and report import outcomes

**MVP Completed | P0 | Dependencies: FF-12, FF-13**

MVP scope basis: Section 3.2 and acceptance criterion 4: idempotent import, rejection reports and preserved prior data.

Description: Support startup/explicit import with stable external-ID upserts and no partial changes after source failure.

Acceptance criteria: Duplicate IDs update existing records/references; accepted distinct records cap at 20; imported/updated/skipped totals are correct; failed traversal preserves previous data.

Testing steps: Run importer idempotence, cap, failure and restart-upsert tests; compare recipe IDs and references before/after import.

Evidence: `1bf7f6e`, `b54a99a`; unique `external_id` and import transaction. Synthetic 20-record tests do not satisfy the live minimum.

### FF-15 - Search, filter and rank backend recipe discovery

**MVP Completed | P1 | Dependencies: FF-09, FF-14**

MVP scope basis: Section 3.2 and acceptance criterion 3: discovery/search, match percentage and ranking.

Description: Display recipe images/categories, original-line match scores and expiry notes with title/category filters and sorting.

Acceptance criteria: Score is rounded adequately-covered/total lines at base scale; urgency breaks ties; unapproved substitutions cannot inflate score; match/title sort works.

Testing steps: Run matching/search/urgency calculations and HTTP integration; reproduce recorded recipe discovery and inspect `recipes.index.tsx`.

Evidence: `1bf7f6e`, `a053f16`, `a507929`. Real recipe variety remains dependent on open corpus work.

### FF-16 - Show recipe details and scale canonical demands consistently

**MVP Completed | P0 | Dependencies: FF-08, FF-15**

MVP scope basis: Section 3.3 and acceptance criterion 6: detail and consistent requested/base scaling.

Description: Return instructions/image/base metadata, scaled requirements and expiry-aware stock for a selection.

Acceptance criteria: Requested numeric scale is integer 1-8; every demand uses requested/base; detail, shopping and cooking share the same calculation.

Testing steps: Run base-servings scaling/shared-demand tests; request multiple scales through the HTTP adapter and compare exact amounts.

Evidence: `1bf7f6e`, `a053f16`, `a507929`; `demands` and recipe detail UI. Numeric scaling is complete; human-portion semantics remain FF-38.

### FF-17 - Suggest eligible substitutions and require explicit confirmation

**MVP Completed | P0 | Dependencies: FF-06, FF-09, FF-16**

MVP scope basis: Section 3.3 and acceptance criterion 6: reviewed eligible substitutions with explicit confirmation.

Description: Apply ten reviewed category-limited rules with ratios/explanations only after user confirmation.

Acceptance criteria: Suggestions require compatible units and enough aggregate usable substitute stock; duplicate/wrong-context/invalid choices fail; confirm/reject/undo controls exist; saved basket choices affect demands.

Testing steps: Run substitution calculations and frontend domain/mock tests; reproduce confirmation/undo in detail and basket.

Evidence: `1bf7f6e`, `a053f16`, `a507929`; rules/category eligibility and choice validation. Restoring saved choices in recipe detail remains FF-40.

### FF-18 - Find and validate the minimum two-real-recipe baseline

**MVP Remaining | P0 | Ready | Dependencies: FF-12, FF-13 | Source worktree | Budget: 0.5 hour**

MVP scope basis: Revised spec 3.2 / criterion 4; original 15-20 breadth is preserved in Post-MVP FF-20.

Description: Inspect promising real TheMealDB payloads for a second fully quantified source recipe, with an ingredient shared with the first. Review every line rather than only the first rejection. Current evidence proves only one accepted raw record (`53137`).

Acceptance criteria: Two distinct source IDs, complete raw responses, provenance and manually checked exact quantities are identified. No synthetic records, silently dropped ingredients, guessed measures/yields or mass/count reinterpretation. If not feasible after 30 minutes, return a concrete blocking report and protect the integration budget; the issue stays open.

Testing steps: Run both raw records through the real normalizer, compare ingredient/quantity expectations independently, and record all rejection reasons. A failed source request is not normalization evidence.

Parallel opportunity: independent of UI work. Output is the reviewed baseline for FF-19; no broad source audit or 15-record inventory is needed for MVP.

### FF-19 - Seed reviewed raw source snapshots through the strict importer

**MVP Remaining | P0 | Blocked by FF-18 | Dependencies: FF-18, FF-14, FF-32, FF-33 | Source worktree | Budget: 1.5 hours**

MVP scope basis: Revised spec 3.2 / criteria 4-5; deterministic baseline without relaxing conversion rules.

Description: Package the reviewed unaltered source responses with provenance; reuse `MealSource`, strict normalization and external-ID upsert to seed only missing baseline IDs without waiting for a whole-alphabet network scan. Keep explicit real live import and its existing error/report contract.

Acceptance criteria: Fresh SQLite starts with at least two valid real recipes offline; repeated initialization adds no duplicates or pantry stock; old snapshots never overwrite newer live records. Only necessary proven aliases are allowed. Existing saved units/IDs/features and strict rejection survive. No new schema, general cache platform, speculative densities, source editing or synthetic production fallback.

Testing steps: Add focused tests for both raw records and explicit expected amounts, ambiguous near-miss rejection, repeat seed, preservation of updated records and malformed baseline rollback; run existing importer/persistence tests. Production bootstrap must not depend on Post-MVP FF-20.

Parallel opportunity: source/catalog/bootstrap code only. Do not edit shared frontend files; coordinate `main.py` and importer tests with QA worktree FF-45.

### FF-20 - Expand source support and regression coverage to 15-20 real recipes

**Post-MVP | P2 | Not scheduled in 12-hour budget | Dependencies: FF-21, FF-48 | v1.1 - Source breadth | Estimate: 6-16 hours after feasibility review**

Post-MVP scope basis: Spec section 9 explicitly moves the original 15-20 count beyond the two-record functional MVP. Strict normalization and all-line completeness remain mandatory; only breadth is deferred.

Description: Broaden the useful real recipe selection and its provenance-backed regression corpus once the complete two-recipe workflow ships. This preserves the original target rather than declaring it accomplished.

Acceptance criteria: 15-20 distinct valid real records, complete metadata, source capture provenance, reviewed identities/amounts and deterministic offline regression expectations. Extend only exact mappings; preserve existing data/units, repeat-import IDs, rejection reports and the API. Include representative supported categories and rejection cases; never guarantee a category unsupported by available data.

Testing steps: Independently inspect raw quantities, normalize/import the full corpus, repeat import and restart, run shared-shopping/cooking cases and record actual live import totals. Synthetic mock counts do not satisfy this issue. Re-estimate if source evidence is insufficient.

Parallel opportunity: optional after MVP acceptance; never a prerequisite for FF-19, FF-21, FF-44 or FF-48.

### FF-21 - Verify baseline startup, real import and restart without duplicates

**MVP Remaining | P0 | Blocked by FF-19 | Dependencies: FF-19, FF-35 | Source worktree | Budget: 0.5 hour**

MVP scope basis: Revised spec 3.2 / criteria 1, 4 and 7; original larger count is Post-MVP FF-20.

Description: Verify normal app startup from a fresh file using the reviewed baseline, live explicit import when available, and reopening the same database.

Acceptance criteria: At least two real records with shared stock are usable with complete metadata; repeated seed/import keeps stable external IDs and references; offline startup does not hang on a full network scan. Live failure preserves data and returns the unchanged failure envelope. Startup diagnostics reflect the revised two-record minimum rather than falsely warning that MVP requires fifteen. Any extra existing valid recipes remain available. Record real source IDs and actual observations, not an invented count.

Testing steps: Start normal FastAPI with a temporary file URL, inspect records, restart, compare IDs/quantities and retry explicit import. Validate offline behavior deterministically; live connectivity failure is recorded honestly while snapshots remain independently source-backed. No 15-record corpus is an MVP dependency.

Parallel opportunity: source owner runs this focused smoke immediately after bootstrap; provide evidence/database instructions to integration owner FF-44.

## M3 - Basket, shopping and cooking


### FF-22 - Implement duplicate-free basket selections with stored choices

**MVP Completed | P0 | Dependencies: FF-16, FF-17**

MVP scope basis: Section 3.4 and acceptance criteria 6-7: unique basket selections and stored choices.

Description: Add/update/remove recipe selections with per-item scale and confirmed substitutions.

Acceptance criteria: Re-adding updates scale instead of duplicating; omitted patch fields stay unchanged; clearing choices is explicit; selected substitutions affect aggregate demands.

Testing steps: Run basket upsert/substitution calculations and persistence tests; re-add at another scale and compare IDs, choices and totals.

Evidence: `1bf7f6e`, `b54a99a`; basket router/service, unique recipe constraint, substitutions JSON. Storage mechanics are documented in M4 rather than treated as missing here.

### FF-23 - Deliver basket selection editing and cumulative requirements

**MVP Completed | P1 | Dependencies: FF-11, FF-22**

MVP scope basis: Section 3.4: editable selections and cumulative ingredient requirements.

Description: Render saved recipes, scale controls, substitute choices, removal, cumulative ingredients and shopping/cooking entry points.

Acceptance criteria: Controls call the shared service; quantities refresh after confirmed changes; loading/error/empty states exist.

Testing steps: Run `src/test/basket-shopping.test.tsx` and HTTP integration; compare cumulative quantities with backend results after changing scale.

Evidence: `a053f16`, `a507929`; `routes/basket.tsx` and recorded browser journey. Reusing choices in recipe detail remains FF-40.

### FF-24 - Aggregate grocery requirements and subtract pantry stock once

**MVP Completed | P0 | Dependencies: FF-09, FF-22**

MVP scope basis: Section 3.5 and acceptance criterion 8: aggregate requirements and subtract pantry once.

Description: Combine canonical basket requirements after applying confirmed substitutions.

Acceptance criteria: Shared ingredients aggregate; usable stock subtracts once; to-buy is clamped at zero; expired stock and incompatible dimensions cannot contribute.

Testing steps: Run shared-pasta, g/kg, ml/l and substituted shopping cases in backend calculations and frontend domain/HTTP tests; assert exact quantities.

Evidence: `1bf7f6e`, `a053f16`; `aggregate`, `basket_demands`, `generate_shopping`.

### FF-25 - Preserve shopping edits and require confirmation before regeneration

**MVP Completed | P0 | Dependencies: FF-24**

MVP scope basis: Section 3.5 and acceptance criterion 9: preserve manual edits and confirm destructive regeneration.

Description: Maintain manual/generated lines, overrides, removal and purchased status through explicit regeneration.

Acceptance criteria: Regeneration resets generated lines and preserves manual ones unless reset is chosen; edited/purchased/removed generated lines or destructive manual reset require `force` confirmation.

Testing steps: Run regeneration and frontend overwrite tests; remove a generated line, reopen the database and verify confirmation remains required.

Evidence: `1bf7f6e`, `a053f16`, `b54a99a`; saved `edited` and `removed_generated` markers with restart coverage.

### FF-26 - Deliver shopping forms and explicit received-purchase confirmation

**MVP Completed | P1 | Dependencies: FF-23, FF-25**

MVP scope basis: Sections 3.5 and 4: explicit received quantity/date and confirmed purchase feedback.

Description: Render shopping lines and confirm actual quantity/expiry before transfer into pantry.

Acceptance criteria: Checking purchased alone changes no pantry stock; catalog-linked lines expose confirmation fields; transfer completion appears only after service success; failed transfer stays recoverable.

Testing steps: Run all five `basket-shopping.test.tsx` cases, especially deferred confirmation and failed transfer; reproduce the recorded purchase journey.

Evidence: `a053f16`, `a507929`; `routes/shopping.tsx`. Feedback improvements in other shopping forms remain FF-42.

### FF-27 - Transfer purchases atomically and exactly once

**MVP Completed | P0 | Dependencies: FF-07, FF-25**

MVP scope basis: Section 3.5 and acceptance criterion 10: atomic exactly-once transfer.

Description: Merge confirmed purchased stock and its completion marker within one inventory transaction.

Acceptance criteria: Catalog linkage, purchased status, quantity and expiry are validated; differing expiry conflicts without changes; retries/concurrency cannot double-add; completion cannot be unchecked.

Testing steps: Run transfer cases in `test_inventory_transactions.py` and durable write-failure/restart/independent-engine tests in `test_persistence.py`.

Evidence: `1bf7f6e`, `b54a99a`; marker and pantry merge share a SQLite transaction. Independent connection tests do not claim multi-machine cloud-sync support.

### FF-28 - Revalidate cooking and atomically deduct stock with history

**MVP Completed | P0 | Dependencies: FF-09, FF-16, FF-17**

MVP scope basis: Section 3.6 and acceptance criterion 11: preview, shortage blocking and atomic deductions/history.

Description: Preview aggregate deductions, then validate current stock again at confirmation.

Acceptance criteria: Any shortage blocks every deduction; scaled/substituted demands aggregate correctly; depleted entries are removed; history and deductions commit together or neither commits.

Testing steps: Run stale-preview, shared-substitute, failure-injection and competing-cook cases; reopen the database after SQL failure to check durable rollback.

Evidence: `1bf7f6e`, `b54a99a`; `preview`, `confirm_cook`, inventory/persistence tests. Cooking is intentionally non-idempotent; uncertain UI outcomes remain FF-41.

### FF-29 - Deliver cooking preview and confirmation from detail and basket

**MVP Completed | P1 | Dependencies: FF-23, FF-28**

MVP scope basis: Section 3.6 and section 4: cooking entry points, deduction preview and truthful success feedback.

Description: Show the selected request's deductions and block confirmation while previewing or short of stock.

Acceptance criteria: Required/available amounts and substitutes are displayed; only confirmed success toasts and refreshes views; both entry points use selected scale/choices.

Testing steps: Reproduce documented blocked/successful cooking; run the HTTP journey; inspect preview cancellation and confirmation disabled states in `CookDialog.tsx`.

Evidence: Component refined in `a053f16` and `a507929`; historical browser evidence. This closes success/blocked paths, not stale/error recovery in FF-41.

### FF-30 - Provide persisted history and dashboard recommendations through the API

**MVP Completed | P1 | Dependencies: FF-15, FF-28**

MVP scope basis: Sections 3.6-3.7 and 5: stored history, dashboard counts/recommendations/recent records.

Description: Store recipe/time/scale/consumption snapshots; return full history plus dashboard counts, recommendations and recent records.

Acceptance criteria: History is newest-first; dashboard contains pantry/soon/expired counts, up to four recommendations and five recent records; no speculative analytics.

Testing steps: Run contract/calculation/persistence tests; cook and verify history/dashboard fields and restart retention; inspect Dashboard presentation.

Evidence: `1bf7f6e`, `a053f16`, `b54a99a`. API returns full history, Dashboard only five recent entries; reaching older records in UI remains FF-43.

### FF-31 - Connect production services to HTTP with recoverable transport errors

**MVP Completed | P1 | Dependencies: FF-03, FF-04, FF-05**

MVP scope basis: Sections 1-2 and 4: real centralized HTTP service, CORS and recoverable failures.

Description: Use the HTTP adapter by default, configurable API origin and local Vite CORS.

Acceptance criteria: All 23 calls preserve quantities/messages and contract encoding; IDs/substitutions encode safely; empty deletes work; errors are recoverable `ServiceError`; no mock fallback on failure.

Testing steps: Run HTTP unit/integration suites, typecheck and API validation; test allowed/disallowed CORS preflights.

Evidence: `a507929`; adapter/hooks, `frontend/.env.example`, backend CORS. This is transport implementation; FF-36 accounts for integration evidence.

## M4 - Persistence and integration

### FF-32 - Persist the specification model with SQLAlchemy and SQLite

**MVP Completed | P0 | Dependencies: FF-05, FF-06, FF-14, FF-22, FF-25, FF-30**

MVP scope basis: Sections 2 and 5: SQLAlchemy/SQLite schema, configurable URL and persisted entities.

Description: Replace authoritative process dictionaries with a relational SQLite unit of work configured by `DATABASE_URL`.

Acceptance criteria: All eight spec tables and internal settings exist; references/numeric canonical columns persist; basket/history JSON preserves API shapes; uniqueness and nonnegative inventory constraints are enforced.

Testing steps: Run `test_persistence.py`, inspect tables/foreign keys and a custom file URL, and rerun unchanged response-schema tests.

Evidence: `b54a99a`; SQLAlchemy Core tables in `app/store.py` and transaction-local state. No PostgreSQL/Docker/authentication was introduced.

### FF-33 - Initialize database and sample seeds without duplicates

**MVP Completed | P1 | Dependencies: FF-32**

MVP scope basis: Sections 2, 3.2 and 5: repeat-safe initialization and seeds that preserve user data.

Description: Create schema/catalog/rules idempotently and seed example pantry only once.

Acceptance criteria: Repeated starts retain 40 ingredient/10 rule rows; recipe external IDs stay stable; an emptied pantry does not repopulate on restart.

Testing steps: Run `test_seed_is_unique_and_deleted_pantry_stays_deleted` and import restart cases; inspect counts after repeated store creation.

Evidence: `b54a99a`; conflict-safe inserts and persistent `pantry_seeded` marker. Seed mechanism is complete; verifying the revised two-real-recipe baseline remains FF-21 and expansion is Post-MVP FF-20.

### FF-34 - Prove durable rollback and serialize competing inventory operations

**MVP Completed | P0 | Dependencies: FF-27, FF-28, FF-32**

MVP scope basis: Sections 3.5-3.6, 5 and acceptance criteria 10-11, 13: durable transaction/inventory evidence.

Description: Protect inventory through real SQL transactions, not just memory rollback or a process lock.

Acceptance criteria: Failure after pantry SQL writes rolls back history/transfer markers; six independent engines cannot overcook or double-transfer; constraints reject negative/duplicate stock.

Testing steps: Run parametrized write-failure/independent-engine/constraint tests and existing threaded inventory tests; reopen file to verify durable rollback.

Evidence: `b54a99a`; `BEGIN IMMEDIATE`, transaction context, explicit SQL failure injection. No crash/power-loss experiment is claimed.

### FF-35 - Prove state survives a new Python process opening the same database

**MVP Completed | P0 | Dependencies: FF-32, FF-33, FF-34**

MVP scope basis: Section 2 and acceptance criteria 1, 7, 10-11: process-restart persistence evidence.

Description: Reopen durable application state with a separate interpreter.

Acceptance criteria: Pantry/expiry, recipes, basket choices, shopping manual/edit/transfer state, history and removed-generated protection survive; transfer retry after reopening adds nothing.

Testing steps: Run `test_all_entities_survive_a_new_python_process` and restart import cases; compare serialized state, not only counts.

Evidence: `b54a99a`; subprocess persistence tests. Synthetic source and service-level process checks are not a full live browser restart journey; see FF-44.

### FF-36 - Verify every service operation through the actual HTTP adapter

**MVP Completed | P0 | Dependencies: FF-31, FF-32, FF-34**

MVP scope basis: Section 2 and acceptance criteria 12-13: real frontend/API integration verification.

Description: Start isolated FastAPI on a free port and exercise production TypeScript calls.

Acceptance criteria: Every operation, CORS, validation, units, expiry, substitutions, regeneration, purchase and cooking are exercised; fixture data cannot touch the developer database.

Testing steps: Run `npm test -- src/services/httpService.integration.test.ts`; inspect file-backed temporary database and synthetic strict source in `backend/tests/http_server.py`.

Evidence: `a507929`, `b54a99a`; both integration cases passed in the original backlog verification. This does not establish the real recipe minimum.

### FF-37 - Document local startup, API configuration and initial SQLite setup

**MVP Completed | P1 | Dependencies: FF-02, FF-31, FF-32, FF-35**

MVP scope basis: Section 2 step 7: local startup, setup and verification documentation.

Description: Document uv/npm startup, API origin/CORS, database URL/schema/seeds/backups and verification.

Acceptance criteria: Instructions explain automatic initial tables, persistence, one-time seeds, absent migration from lost memory/mock data and live import limitations honestly.

Testing steps: Compare README commands with scripts/env reads; reproduce startup against isolated new/existing databases. Current tests and preceding build support the documented toolchain.

Evidence: `1bf7f6e`, `a507929`, `b54a99a`; READMEs/integration notes. Final acceptance results and stale explanatory prose are FF-47.

## M5 - Completion and focused acceptance

### FF-38 - Label exact recipe-batch scaling without invented servings

**MVP Remaining | P1 | Ready | Dependencies: FF-16 | Frontend worktree | Budget: 0.5 hour**

MVP scope basis: Revised spec 3.3 / criterion 6; batch interpretation is now explicit rather than an unresolved human-yield dependency.

Description: Keep numeric API `servings`/`base_servings` and scaling unchanged. Describe unyielded TheMealDB records as whole-source batches in detail, basket, cook preview and recent history.

Acceptance criteria: One batch uses all source quantities; selection 1-8 scales by the exact existing ratio; no UI claims how many people it serves. Existing layout/API is preserved. No yield scraping, inference, human-portion conversion or new metadata system is needed.

Testing steps: Check labels and quantities at one and two batches across detail/basket/shopping/preview/history; retain scale tests and add one focused label assertion. Confirm stored historical numeric values are not reinterpreted or rewritten.

Parallel opportunity: frontend owner also handles FF-40 to avoid conflicting detail edits; no need to wait for a source-yield study.

### FF-39 - Keep expiry configuration and visible statuses consistent

**MVP Remaining | P1 | Ready | Dependencies: FF-09, FF-10, FF-30 | Frontend worktree | Budget: 0.5 hour**

MVP scope basis: Spec 3.1 / criteria 2-3; existing backend configurability is preserved, not removed for time.

Description: Coordinate the existing server threshold with a documented frontend launch/build value and replace misleading hardcoded numeric notes as needed. Default remains three days.

Acceptance criteria: Pantry filters/badges, recipe notes and dashboard agree at default and one non-default setting; invalid threshold values fail clearly. No settings screen, extra API or backend feature removal.

Testing steps: Test thresholds three/five with boundary stock and compare backend counts with UI labels/status. Check documented paired configuration and default behavior.

Parallel opportunity: frontend owner can share copy edits with FF-38; source work is independent.

### FF-40 - Preserve basket selections and recover from partial detail updates

**MVP Remaining | P0 | Ready | Dependencies: FF-17, FF-22, FF-23 | Frontend worktree | Budget: 1 hour**

MVP scope basis: Spec 3.3-3.4 and 4 / criteria 6-7, 12; saved choices and truthful updates are core functionality.

Description: Recipe detail currently starts from defaults and performs add/upsert followed by a substitution patch. Restore an existing selection before editing and prevent silent clearing or misleading success after a partial action.

Acceptance criteria: Existing choices/scale are shown and preserved unless changed; existing selections use the existing patch for coordinated edits. A new-item second-call failure is visible and reconciled with actual server state, without pretending the contract provides atomic multi-request updates. Route changes clear unrelated local choices. No new endpoint or UI redesign.

Testing steps: Reopen a saved nondefault selection, change only scale, inject patch failure after add, then reload/navigate. Assert correct totals, preserved choices, recovery feedback and no false success.

Parallel opportunity: same frontend owner as FF-38; independent from source/bootstrap work.

### FF-41 - Reconcile cooking failures without retrying uncertain deductions

**MVP Remaining | P0 | Ready | Dependencies: FF-28, FF-29, FF-31 | Frontend worktree | Budget: 1 hour**

MVP scope basis: Spec 3.6 and 4 / criteria 11-12; stale or uncertain outcomes cannot be Post-MVP.

Description: CookDialog failure currently toasts without reconciling preview/pantry/history. Preserve server atomicity while making the client recover safely.

Acceptance criteria: A rejected confirmation invalidates/reloads affected data and preview; preview errors offer retry. After a lost confirmation response, check history/current state before another deliberate action; never automatically repeat non-idempotent cooking or claim failure proves nothing committed. Success remains backend-confirmed only.

Testing steps: Inject stale-stock 409, preview failure/retry, and a server commit with dropped response. Verify reconciliation, no automatic duplicate cook, no negative inventory and preserved normal success behavior.

Parallel opportunity: isolated component, but frontend owner coordinates any shared hooks. Do not add a new cooking-idempotency API under the deadline.

### FF-42 - Finish actionable inline feedback in existing pantry/shopping forms

**MVP Remaining | P1 | Ready | Dependencies: FF-10, FF-26, FF-31 | Frontend worktree | Budget: 0.5 hour**

MVP scope basis: Spec 4 / criterion 12; validation and recoverable rejected mutations remain required.

Description: Reuse current validation and service errors to keep forms recoverable; avoid a form-framework rewrite.

Acceptance criteria: Backend rejection leaves inputs intact and displays actionable inline quantity/date/expiry-conflict feedback as well as existing notifications. Pending actions cannot show premature success. Keep current visual design and validation rules.

Testing steps: Reject a pantry save and shopping quantity edit, correct in place and resubmit. Assert retained values, visible error and one confirmed success; keep deferred purchase tests passing.

Parallel opportunity: frontend owner can batch these small form changes, independent of source/QA worktrees.

### FF-43 - Add a complete older-history browser within the existing UI

**Post-MVP | P2 | Not scheduled in 12-hour budget | Dependencies: FF-30, FF-35, FF-38, FF-48 | v1.1 - History depth | Estimate: 1-2 hours**

Post-MVP scope basis: Spec section 9 explicitly narrows MVP presentation to existing recent history. Every record and the full history API remain working MVP features; no data or API access is deferred or removed.

Description: Add an expansion or equivalent simple view for older records after the complete MVP ships. This is extra presentation depth, not a fix for lost cooking history.

Acceptance criteria: More than five stored records can be browsed newest-first with recipe/date/batch count; loading/empty/error states work. Reuse `listHistory`; no new analytics, schema or sidebar redesign. If actual storage/history API loss is found, treat that defect as MVP instead of hiding it here.

Testing steps: Create six-plus records, verify older rows across reload/restart and error handling, and confirm Dashboard remains unchanged by default.

Parallel opportunity: optional and isolated to Dashboard/history presentation after FF-48; not a release dependency.

### FF-44 - Verify the complete two-real-recipe workflow through SQLite restart

**MVP Remaining | P0 | Blocked on source and core UI fixes | Dependencies: FF-21, FF-35, FF-36, FF-38, FF-39, FF-40, FF-41, FF-42 | Integration worktree | Budget: 1 hour**

MVP scope basis: Revised spec criterion 13 and criteria 1-12; final evidence is mandatory, not optional polish.

Description: Run the established UI through Pantry -> Recipes -> Basket -> Shopping -> Purchase -> Cook -> Restart with the real reviewed baseline. Prepare the checklist while implementation runs.

Acceptance criteria: Two real records demonstrate shared-stock subtraction once, exact batch scaling, expired-stock exclusion, edit protection, actual purchase quantity/expiry, idempotent transfer and atomic history/deductions. Reload/restart preserves selections/data. Exercise substitution with a compatible real recipe if available; otherwise document a separately labeled strict deterministic test supplement, never a fictional production recipe. No failed core path is accepted to meet the clock.

Testing steps: Record source IDs plus before/after inventory/history snapshots; restart the same file; retry completed transfer; reproduce blocked cooking and accurate error recovery. Use existing browser tooling rather than building a new platform.

Parallel opportunity: prepare early; execute only against merged work. Post-MVP FF-20 and FF-43 are explicitly not prerequisites.

### FF-45 - Verify offline startup and failed live import retain durable data

**MVP Remaining | P0 | Ready to prepare; run after bootstrap integration | Dependencies: FF-14, FF-19, FF-32, FF-35 | QA worktree | Budget: 0.5 hour**

MVP scope basis: Revised spec 3.2 and persistence criteria; offline baseline usability and retained user data are required.

Description: Reuse current persistence/failure test patterns for the new baseline source; no broad resilience platform.

Acceptance criteria: Fresh offline startup has the real baseline; an existing database with user data opens without waiting for live traversal. A failed explicit live import preserves recipes, basket, shopping, pantry/history and returns the existing error. Seeds never overwrite newer source records or refill empty pantry.

Testing steps: Inject bounded offline/malformed upstream failures against fresh and saved file-backed apps; compare snapshots and repeated seed counts. Keep previous source-failure tests rather than weakening their guarantees.

Parallel opportunity: QA owner prepares an isolated new test file; run final cases after cherry-picking source commit. Source owner owns `main.py` and existing importer tests to avoid edit conflicts.

### FF-46 - Smoke-test responsive navigation and critical forms/confirmations

**MVP Remaining | P1 | Ready to prepare | Dependencies: FF-11, FF-23, FF-26, FF-29, FF-38, FF-39, FF-40, FF-41, FF-42 (prepare early) | QA worktree | Budget: 0.5 hour**

MVP scope basis: Spec 1 and 4; usable responsive core controls remain mandatory.

Description: Verify existing layout on desktop and a narrow viewport with simple keyboard interaction. No redesign or accessibility-certification project.

Acceptance criteria: All five destinations, ingredient/batch controls, purchase date/quantity and cook/overwrite confirmations are usable, including cancel/error states. Long report content remains reachable. Any reproduced blocker stays MVP and uses reserve; cosmetic enhancements are not created to consume the budget.

Testing steps: At desktop and 375px width navigate, tab, submit/cancel and recover from one error; record browser/viewport/results and rerun affected controls after merged fixes.

Parallel opportunity: inspect stable paths early; final smoke uses integrated frontend commits, not an isolated stale branch.

### FF-47 - Record final setup, batch/source boundary and acceptance evidence

**MVP Remaining | P1 | Blocked on acceptance evidence | Dependencies: FF-44, FF-45, FF-46 | Integration owner | Budget: 0.5 hour**

MVP scope basis: Spec 2 and 7; accurate setup/results required for the working deliverable.

Description: Update final READMEs/integration evidence and explanatory stale API prose during implementation, without changing API structure. Only the two requested planning documents are changed in the present task.

Acceptance criteria: Explain snapshot provenance/missing-ID seeding, real live import errors, batch labels, database/configuration/restart behavior, revised two-record minimum and deferred breadth/history UI. Preserve earlier evidence as historical and record actual final results/warnings/blockers. Never claim the original 15-20 target is done.

Testing steps: Follow documented local startup against a clean file, compare structural OpenAPI fields and map every acceptance statement to real evidence. Do not spend this time on unrelated documentation rewrites.

Parallel opportunity: integration owner drafts while tests run; fill results only after gates complete.

### FF-48 - Run final regression and enforce the 12-hour delivery gate

**MVP Remaining | P0 | Blocked on required gates | Dependencies: FF-47 (transitively all remaining MVP work) | Integration owner | Budget: 0.5 hour**

MVP scope basis: Revised spec 7-9; correctness is never traded for the deadline.

Description: Check the integrated changes and stop at the aggregate time cap with an honest accepted/blocked decision.

Acceptance criteria: All revised MVP criteria have evidence; all existing operations/features/data-integrity tests survive. Two real baseline recipes are proven and batch semantics are truthful. Every MVP Remaining item meets its criteria; Post-MVP FF-20/FF-43 are not falsely marked done. Record actual combined worktree effort and reserve consumed. If a core blocker remains or time expires, report incomplete MVP instead of shipping a broken core.

Testing steps: Run backend pytest/Ruff/format plus frontend tests/typecheck/API validation/lint/build once against merged changes; inspect baseline/restart/browser evidence and final diff. Record actual counts rather than assuming earlier 99/47 results still apply. No GitHub creation, deployment, publishing or release tagging is authorized by this issue.

Parallel opportunity: final join only; execute after source, frontend and QA commits are integrated. Existing test tools make this a verification timebox, not an invitation to build infrastructure.


## Revised MVP acceptance coverage

| Criterion / preserved feature | Delivered foundation | Required closure under this boundary |
| --- | --- | --- |
| Pantry CRUD, compatible units, filters, visible expired items | FF-06 to FF-10 | FF-39 configuration, FF-42 feedback, FF-44 end-to-end |
| Strict real-source recipes and metadata | FF-12 to FF-16 | FF-18/FF-19/FF-21 prove two distinct real records with shared stock; FF-20 is optional corpus breadth |
| Exact scaling and explicit eligible substitutions | FF-16/FF-17/FF-22 | FF-38 batch labels, FF-40 saved choices, FF-44 real journey plus clearly labeled substitution supplement if necessary |
| Persistent basket/shared groceries | FF-22 to FF-25, FF-35 | FF-40 partial-update recovery and FF-44 exact shared-stock test |
| Manual shopping edits and exactly-once received purchase | FF-25 to FF-27, FF-34/FF-35 | FF-42 and FF-44; never defer a duplicate-transfer bug |
| Atomic revalidated cooking and durable history | FF-28/FF-30, FF-34/FF-35 | FF-41 uncertain-outcome recovery, FF-44/FF-45; all records/full API retained |
| Recent Dashboard history and recommendations | FF-15/FF-30 | Batch/threshold labels; FF-43 adds optional older-history UI, not storage |
| SQLite URL, seeds, restart and upstream failure | FF-32 to FF-37 | FF-19 missing-only source baseline, FF-21 repeat startup, FF-45 offline data retention |
| Standard API/transport, inline errors and responsive UI | FF-04/FF-05/FF-11/FF-31/FF-36 | FF-39 to FF-42, FF-46; no structural contract change |
| Full journey, tests and truthful documentation | Existing 99 backend / 47 frontend historical evidence | FF-44 to FF-48 must record new integrated results; no automatic reuse of old pass counts |

No issue classified Post-MVP is reachable as a release prerequisite. Conversely, an inventory/history/choice-loss bug discovered while implementing a Post-MVP enhancement is core MVP work and must be reported/fixed under the appropriate integrity gate.

## Dependency order and minimum critical path

1. **Immediately: FF-18, with a 30-minute stop/go gate.** If two strict real records cannot be established, report that result before expanding the investigation. Do not run open-ended discovery, add a different source, reinterpret quantities or claim a seed exists.
2. **Source branch: FF-18 -> FF-19 -> FF-21**, nominal 2.5 engineering hours. Baseline fixtures/rejection/idempotency tests are in these MVP tasks, not deferred with the larger FF-20 corpus.
3. **Frontend branch: FF-38/FF-39/FF-40/FF-41/FF-42**, nominal 3.5 engineering hours for one owner. Do detail labels and saved-selection edits together; CookDialog and form feedback remain core. Batch semantics now remove the human-yield research dependency.
4. **QA branch:** prepare FF-45 after the source interface is agreed, run it after FF-19; prepare FF-46 early, finish affected control checks after frontend merge. Neither depends on optional features.
5. **Join:** FF-21 and all frontend fixes -> FF-44. FF-44/FF-45/FF-46 -> FF-47 -> FF-48. Preserve completed milestones; do not rebuild them.

The source dependency chain **FF-18 -> FF-19 -> FF-21 -> FF-44 -> FF-47 -> FF-48** is **4.5 nominal serial engineering hours**. With one frontend owner the 3.5-hour frontend branch can dominate the join, making the illustrative resource-constrained elapsed path **5.5 hours before handoffs/overruns**. These figures assume source feasibility and ready tooling, not proof that tasks will fit. Plan roughly **6-9 elapsed working hours with parallel worktrees**, while enforcing the separate **12 aggregate engineering-hour** cap. Waiting for data or decisions can still miss the deadline; elapsed estimates are conditional.

With one contributor, nine planned engineering hours plus up to three reserve gives a conditional 9-12-hour completion attempt. Parallelism changes handoffs and elapsed time, not the sum of actual effort. Source feasibility and undiscovered core defects can invalidate that attempt; there is no guaranteed twelve-hour solution if the stop/go gate fails.

## Strict budget ledger

| Issue | Priority | Immediate prerequisite | Nominal engineering hours |
| --- | --- | --- | ---: |
| FF-18 | P0 | Existing strict importer | 0.5 |
| FF-19 | P0 | FF-18 | 1.5 |
| FF-21 | P0 | FF-19 | 0.5 |
| FF-38 | P1 | Existing scaled detail | 0.5 |
| FF-39 | P1 | Existing expiry behavior | 0.5 |
| FF-40 | P0 | Existing persisted basket | 1.0 |
| FF-41 | P0 | Existing atomic cooking | 1.0 |
| FF-42 | P1 | Existing forms/service errors | 0.5 |
| FF-44 | P0 | Source/UI merge | 1.0 |
| FF-45 | P0 | FF-19; prepare independently | 0.5 |
| FF-46 | P1 | Integrated affected UI | 0.5 |
| FF-47 | P1 | FF-44/FF-45/FF-46 | 0.5 |
| FF-48 | P0 | FF-47 | 0.5 |
| Planned remaining work | 13 issues | Includes focused tests and final verification | **9.0** |
| Shared reserve | No added feature | Planning/setup time not already counted, worktree integration, defects/rechecks | **3.0** |
| Hard aggregate cap | All contributors combined | Not twelve hours per agent | **12.0** |

Record actual time once per task/contributor; debit planning/setup/coordination and the final merge/test work too. The repository has no trustworthy prior effort ledger; this table is a forward allocation, not an assertion that a measured twelve hours remain after all earlier work. Deduct already consumed time before implementation starts. Do not reset the cap after a failed audit. The original full-scope estimate (20-43 base / 25-55 with contingency) is preserved as history below; nine hours is a smaller-scope, timeboxed attempt rather than a retrospective proof that the old work was faster.

At the nominal six aggregate engineering hours used by source/frontend changes, freeze optional edits and move to integrated acceptance. Protect the planned three hours of QA/docs/final verification. Reserve is for correctness only. At aggregate hour twelve stop, record actual state and report accepted or blocked; never skip a critical failing check or recategorize a broken core to fit.

## Safe parallel agents in separate Git worktrees

This is a future execution design only. No agents or worktrees are started by this documentation task. A coordinator plus up to three agents is enough; more concurrency adds unnecessary handoffs for this small change.

| Owner / suggested branch and worktree | Issues and exclusive edits | Safe parallel work / constraints |
| --- | --- | --- |
| Source agent: `mvp/source`, sibling `freshfirst-source` | FF-18/FF-19/FF-21; `backend/app/services/importer.py`, minimal catalog aliases, source snapshot data, `backend/app/main.py` bootstrap, related existing importer/seed tests | Independent of frontend. Preserve store transaction design and API; no schema/canonical-unit changes. Own existing importer tests and startup file so QA does not edit them concurrently |
| Frontend agent: `mvp/frontend`, sibling `freshfirst-frontend` | FF-38/FF-39/FF-40/FF-41/FF-42; detail/basket/history labels, CookDialog, forms, hooks and focused frontend tests; paired frontend env example if needed | Same owner for shared detail/hooks files. Source owner coordinates server threshold validation without simultaneous edits. No design changes, new service signatures, package updates or lockfile churn |
| QA agent: `mvp/acceptance`, sibling `freshfirst-acceptance` | FF-45/FF-46 preparation; new isolated startup acceptance test file and evidence supplied to coordinator | Start from reviewed base; cherry-pick source/frontend commits before dependent final checks. Do not edit source-owned `main.py`, existing seed fixtures or frontend-owned components; report reproduced bugs to their owner |
| Coordinator: integration branch/worktree | Merge/cherry-pick reviewed commits, FF-44/FF-47/FF-48, both planning documents and final README/integration evidence | Final acceptance runs on the combined commit, not independent branch passes. Sole owner of shared release docs and final decisions. No force pushes, rebases or amend of published history |

Create each worktree from the same reviewed base, with its own branch and absolute worktree-local SQLite `DATABASE_URL`. Use its own uv environment/frontend install and unique free server ports. Test fixtures must never point to a user's database or another agent's file. Do not share `.venv`, `node_modules`, generated build directories or running servers across worktrees; immutable package download caches may be shared. Keep active databases local rather than concurrently editing cloud-synced copies.

Integrate source and frontend first, run the QA test on that combined state, then the browser journey and full checks. QA bug fixes return to the owning worktree and consume reserve; do not have two agents patch the same component in parallel. Stop agents when their bounded deliverables are complete. Time spent by each agent counts toward the same ledger.

## Genuine Post-MVP v1.1+ backlog

- **FF-20, P2:** expand from the complete two-real-recipe workflow to 15-20 strictly supported real recipes, with reviewed mappings and a larger provenance/regression corpus. The original count remains unfulfilled until this issue actually passes.
- **FF-43, P2:** expose all older saved cooking records in a simple UI browser using the already available full history API. Dashboard recent history, all durable records and API access remain MVP features.

No artificial additional issues are added. Verified human-portion metadata could be a later independently specified enhancement, but this plan does not invent an estimation feature or duplicate FF-38. Existing explicit non-goals remain excluded; they are not promises for v1.1. The two Post-MVP issues wait for FF-48 and are not scheduled within twelve hours.

## Scope-decision change log - original decisions preserved

Original scope/specification is preserved in Git at `13508ba` / `18d4955`. Original backlog is `9a89f63`; the strict unchanged-spec classification (33 completed / 15 remaining / 0 Post-MVP) is `18d4955`. This revision is requested scope planning, not implementation or source evidence.

| Decision | Original / preceding plan | Revised decision and issue impact |
| --- | --- | --- |
| Production recipe count | 15-20 supported real recipes mandatory; FF-18 to FF-21 serial source branch | Two distinct real recipes with shared stock are the functional MVP floor; FF-18/FF-19/FF-21 remain P0. FF-20 retains 15-20 expansion as Post-MVP P2. Original count is explicitly not marked done |
| Source regression tests | FF-20 held the large 15-20 raw-source corpus and related evidence | Mandatory two-record expected-quantity/rejection/idempotent seed tests now belong to FF-19/FF-21; none are deferred with the larger corpus |
| Startup connectivity | Initial import required network; previous data stayed usable offline | Source acquisition/review still real; reviewed raw snapshots may seed missing IDs offline. Preserve real explicit live import/failure semantics and all stored records; no fake fallback success |
| Human servings | Batch-versus-human-yield interpretation blocked FF-38 closure | Whole-source-batch 1-8 is the explicit MVP meaning when yield is absent. Correct UI labels remain MVP; no guessed human yield or extra schema |
| History browser | Previous unchanged-spec plan required older-history UI in FF-43 | Recent Dashboard list is sufficient MVP UI; all persisted records and full API stay intact. Only added older-history presentation becomes Post-MVP FF-43 |
| Existing functionality / data integrity | Complete working APIs/features and strict normalization mandatory | Unchanged. FF-40/FF-41 are elevated P0; form feedback, threshold consistency and responsive checks stay mandatory. No broken core is moved to Post-MVP |
| Estimated effort | Prior unchanged-scope estimate 20-43 base / 25-55 with contingency; serial path 12-25 | Reduced, bounded attempt: nine planned aggregate engineering hours + three reserve. Source serial path 4.5 nominal hours; one frontend owner may make elapsed join 5.5 before overhead. Feasibility can still fail |
| Issue count | 48 issues, 33 MVP Completed / 15 MVP Remaining / 0 Post-MVP | Same stable 48 IDs: 33 / 13 / 2. No manufactured tasks, duplicate endpoint issues or claim that deferred goals are complete |

No application changes, current source fetches, new test executions, worktree creation or GitHub issue creation are performed by this document change. Completed commit/test evidence remains historical and unchanged. The operative acceptance criteria are the revised `docs/spec.md`, not an assertion that the original larger scope has been delivered.

## Risks and stop conditions

1. **Second real source record is unproven.** Historical accepted record `53137` is not two records; another captured fixture is rejected. If a second record needs guessed units or absent identities beyond bounded exact aliases, the source gate fails. Reserve is not permission for an open-ended search or a synthetic production recipe.
2. **Raw snapshot bootstrap is a proposed change, not existing functionality.** It must preserve live imports, missing-only seeds, later source updates, transactional rollback and offline startup. A duplicate/overwrite regression is P0.
3. **Partial/uncertain actions need real recovery tests.** Two-request basket edits and a lost cooking response cannot be deemed safe from a toast alone; discovering larger fixes can exceed one-hour timeboxes.
4. **Worktree setup/merges and local browser/runtime availability cost time.** Keep one owner per file area, reuse installed tooling appropriately per worktree and protect the final verification allocation. Parallel agents do not multiply the budget.
5. **Deadline does not imply correctness.** Stop and report a blocked/incomplete MVP if any core criterion remains unmet or the cap expires. Do not count optional issue deferral as evidence that the two-recipe minimum, exact batch scaling or durable workflows already work.

## Future GitHub handling

This remains a local draft. If later explicitly authorized, create the six grouping milestones plus a v1.1 milestone for FF-20/FF-43, map local references to real issue links, preserve completed evidence and close only the 33 genuinely completed issues. Keep all 13 MVP Remaining and both Post-MVP issues open until their criteria are met. No publishing, GitHub writes, release tags or history rewriting are authorized by this planning task.
