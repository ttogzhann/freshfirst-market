# FreshFirst v1.0 GitHub Issues plan - MVP classification

MVP classification revision for review, 2026-10-20. Original backlog: documentation commit `9a89f63`. Reviewed application commit: `b54a99a4cd4b647fdca6c1f2f7b72570a2e4a94e` on local `main`. FF identifiers below are local planning references, not GitHub issue numbers. No GitHub issues or milestones have been created. This document changes no application behavior.

## Summary

**48 proposed issues: 33 MVP — Completed, 15 MVP — Remaining, 0 Post-MVP.** The count follows independently reviewable project outcomes, rather than one issue per endpoint, recipe, ingredient, component or test. Every existing issue has been reviewed against the unchanged v1.0 specification. All 48 bounded outcomes are required implementation or acceptance evidence; none is an optional enhancement. No mandatory item was deferred and no extra issue was invented to populate Post-MVP. Completed entries reconstruct delivery history; they are not new work to execute. If issue creation is later authorized, attach evidence and close those entries; keep remaining entries open until their acceptance criteria are met.

Most infrastructure and inventory workflows are delivered. **FreshFirst v1.0 is not fully accepted:** the required 15-20 real, fully quantified TheMealDB recipes have not been demonstrated. Remaining work also includes serving semantics, focused frontend corrections and final browser acceptance with real recipes and SQLite restart.

| Milestone | Issue range | MVP — Completed | MVP — Remaining | Post-MVP | Completion condition |
| --- | --- | ---: | ---: | ---: | --- |
| M0 - Specification and architecture | FF-01 to FF-05 | 5 | 0 | 0 | Preserve delivered baseline |
| M1 - Pantry and application shell | FF-06 to FF-11 | 6 | 0 | 0 | Implementation delivered; responsive verification in M5 |
| M2 - Recipes and supported live import | FF-12 to FF-21 | 6 | 4 | 0 | 15-20 valid real recipes with provenance and strict normalization |
| M3 - Basket, shopping and cooking | FF-22 to FF-31 | 10 | 0 | 0 | Core delivered; specific UX corrections in M5 |
| M4 - Durable storage and integration | FF-32 to FF-37 | 6 | 0 | 0 | Preserve persistence/integration evidence |
| M5 - MVP acceptance gaps and sign-off | FF-38 to FF-48 | 0 | 11 | 0 | Mandatory corrections and final evidence complete |
| Total | 48 | 33 | 15 | 0 | M2 and M5 remain open |

### Status and priorities

- **MVP — Completed:** mandatory implementation/evidence is present at the reviewed application commit. Preserve its commits and tests. This does not assert automated component coverage for every interaction or close a separately identified gap.
- **MVP — Remaining:** required implementation, correction or acceptance evidence is not complete. Readiness is tracked separately as ready or blocked. Verification-only issues do not assert an undiscovered defect exists.
- **Post-MVP:** optional enhancement beyond the current specification. **No existing issue qualifies** after limiting each to its stated v1.0 outcome. Zero is deliberate, not an instruction to invent future work.
- **P0:** blocks v1.0 acceptance or protects inventory correctness. Completed priorities record importance, not work to reopen.
- **P1:** mandatory user-facing correctness, responsive/recoverable UX, documentation or verification needed before MVP sign-off. The former P2 remaining items FF-42, FF-46 and FF-47 are P1 because their bounded outcomes are required, even though they can follow the main implementation work.
- Dependencies use FF identifiers; completed dependencies are already satisfied. Milestone numbers group work, not a mandatory serial order. Transitive prerequisites remain mandatory even where final gate metadata lists only its immediate predecessor.

### Classification boundaries

FF-38 resolves truthful base-serving/scaling semantics under sections 3.2-3.3; speculative yield estimation is not its acceptance criterion. FF-39 fixes an existing configured-threshold inconsistency required by section 3.1, without adding a settings UI. FF-40/FF-41 protect stored selections and recovery from partial or uncertain outcomes under sections 3.3-3.6 and 4. FF-42 supplies required inline validation. FF-43 makes the section 3.6 simple history list reachable, without analytics. FF-44/FF-45/FF-46 verify required journeys, offline data retention and usable responsive controls. FF-47/FF-48 supply the documentation and acceptance evidence required by sections 2 and 7.

These issues are not permission for a redesign, an unrestricted recipe catalog, a new settings product, a broad accessibility certification program or a new browser-testing platform. Those additions are unnecessary for their MVP acceptance criteria and are not added as Post-MVP issues. Explicit non-goals remain excluded rather than silently becoming future commitments.

Retain the 23-operation contract, existing response schemas, single-user scope and frontend design. No authentication, deployment, Docker, PostgreSQL, CI/CD project, new integrations, nutrition, calendar or charts. Keep approximately 25-40 supported ingredient identities. Never omit ingredient lines, invent recipes, guess densities or interpret ambiguous packages to reach a count.

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

Preserved verification from the original backlog review at application commit `b54a99a` (recorded in `9a89f63`); no application tests were rerun for this classification-only edit:

- Backend `uv run --locked pytest -q`: **99 passed**. Ruff check/format check passed for 25 Python files. Existing Starlette TestClient/httpx deprecation warning remains.
- Frontend `npm test`: **47 passed in six files**. Typecheck and API validation passed; validation reports **23 operations** with no authentication.
- ESLint and production build passed in the preceding storage verification at the same application commit; not rerun for this documentation-only review. Existing six Fast Refresh warnings/build notices are not new blockers.
- `docs/integration.md` records an earlier browser walkthrough using a synthetic strictly quantified recipe before SQLite, plus separate automated SQLite verification. It does not claim a combined real-source browser/backend-restart acceptance run.
- `backend/README.md` records a historical live audit: **790 fetched, one accepted**. This is not a live count rechecked today. Two real raw fixtures do not prove 15 supported recipes.
- Mock tests accepting 15-20 bundled records and synthetic backend tests accepting 20 establish mechanics only, not production source sufficiency.

No live TheMealDB fetch was made during the original planning or this classification review. Proposed live audit and source-dependent work remain open. Python commands below run from `backend/`; npm commands from `frontend/`. Completed-issue testing steps explain reproduction, not additional backlog tasks.

## M0 - Specification and architecture

### FF-01 - Establish v1.0 scope and the acceptance matrix

**MVP — Completed | P1 | Dependencies: none**

MVP scope basis: Sections 1-2 and 7-8: scope, workflow and explicit acceptance matrix.

Description: Define local single-user journeys, canonical quantities, phased workflow and non-goals.

Acceptance criteria: Specification covers pantry, import, substitutions, basket, shopping, cooking/history and dashboard; expiry and ambiguity restrictions are explicit; no additional product scope is implied.

Testing steps: Compare `docs/spec.md` sections 1-8 with the API and coverage matrix below. Check unresolved count/yield questions are not accepted silently.

Evidence: `13508ba`; `docs/spec.md`, `AGENTS.md`. The historical 12-hour aspiration is not a remaining-work guarantee.

### FF-02 - Organize reproducible frontend and backend environments

**MVP — Completed | P1 | Dependencies: FF-01**

MVP scope basis: Section 2: repository layout, uv/npm setup and reproducible local workflow.

Description: Separate project directories and establish tracked npm/uv lockfile workflows.

Acceptance criteria: Frontend and backend have their documented locations; one documented lockfile/install procedure exists for each; startup and verification commands are supplied.

Testing steps: Reproduce `uv sync --locked` and tests; run `npm ci`, typecheck and build in a disposable checkout. Do not change dependencies merely to clear notices.

Evidence: `16ec563`, `a053f16`, `1bf7f6e`; READMEs, `frontend/package-lock.json`, `backend/uv.lock`. The original backlog verification used installed dependencies, not a fresh npm reinstall; no install was repeated for classification.

### FF-03 - Provide one typed frontend service boundary and injectable mock

**MVP — Completed | P1 | Dependencies: FF-01**

MVP scope basis: Sections 1-2: centralized frontend service interface and tested mock phase.

Description: Centralize calls behind `FreshService` for transport-independent UI and isolated tests.

Acceptance criteria: Screens call through the service/hooks layer; mock and HTTP implementations share types; tests can inject a service; production never silently substitutes mock success after API failure.

Testing steps: Run frontend mock/domain tests; inspect `services/types.ts`, `index.ts` and production selection.

Evidence: Existing frontend retained by `16ec563`, refined by `a053f16` and `a507929`; mock suite passes. Mock recipe counts do not establish the live corpus.

### FF-04 - Author and validate all 23 public OpenAPI operations

**MVP — Completed | P0 | Dependencies: FF-03**

MVP scope basis: Sections 2 and 6: authored OpenAPI operations, schemas and errors.

Description: Define methods, models, statuses, query encoding and errors without authentication.

Acceptance criteria: Exactly 23 operations match `FreshService`; field names/arrays match callers; validation/conflict errors follow the standard envelope.

Testing steps: Run `npm run validate:api` and `uv run pytest -q tests/test_contract.py`; compare registered routes as well as the served authored document.

Evidence: `5153960`, `a053f16`, `1bf7f6e`; OpenAPI 3.0.3 and actual response-schema validation. Stale descriptive prose is FF-47.

### FF-05 - Implement modular FastAPI routing and shared error handling

**MVP — Completed | P1 | Dependencies: FF-04**

MVP scope basis: Sections 2, 4 and 6: modular FastAPI implementation and consistent API validation.

Description: Route catalog, pantry, basket, shopping and cooking into domain services with consistent validation/errors.

Acceptance criteria: Operations exist under `/api`; missing resources, invalid inputs and conflicts return documented statuses/envelopes; unexpected failures never report success.

Testing steps: Run `tests/test_contract.py` and `tests/test_validation.py`; exercise malformed queries, absent resources and null/invalid patches.

Evidence: `1bf7f6e`; `app/main.py`, routers, `models.py`, `errors.py`; current backend suite passes.

## M1 - Pantry and application shell

### FF-06 - Define the supported canonical ingredient catalog

**MVP — Completed | P1 | Dependencies: FF-01, FF-05**

MVP scope basis: Sections 3.1, 3.2 and 5: predefined supported identities and canonical units.

Description: Provide a small stable catalog with category, identity and canonical stock dimension.

Acceptance criteria: Forty identities have stable IDs and g/ml/pcs units; API lists them; only explicit aliases map upstream names to supported identities.

Testing steps: List ingredients; inspect `app/catalog.py`; run importer identity cases and persistence seed-count assertions.

Evidence: `1bf7f6e`, `b54a99a`; catalog/schema tests. Whether this catalog supports 15 real recipes remains FF-18/FF-19.

### FF-07 - Implement pantry CRUD and one entry per ingredient

**MVP — Completed | P0 | Dependencies: FF-06**

MVP scope basis: Section 3.1 and acceptance criteria 1-2: pantry CRUD and one expiry batch per ingredient.

Description: Create, replace and delete pantry stock, merging compatible quantities only at the same expiry.

Acceptance criteria: Equal-expiry additions combine; different expiry conflicts without mutation; edits cannot duplicate another ingredient; expired entries stay editable/removable.

Testing steps: Run pantry validation/contract tests; add 0.1 kg plus 100 g with equal dates, then conflicting dates, and compare quantities.

Evidence: `1bf7f6e`; pantry router, `merge_pantry`, validation tests; database uniqueness in `b54a99a`.

### FF-08 - Validate quantities, calendar dates and compatible units

**MVP — Completed | P0 | Dependencies: FF-05, FF-06**

MVP scope basis: Sections 3.1-3.2 and 4: positive canonical quantities, valid dates and compatible units.

Description: Normalize only supported dimensions with decimal arithmetic and reject invalid inventory inputs.

Acceptance criteria: Quantities are positive and finite; real calendar dates are required; g/kg and ml/l/kitchen-volume table normalize; dimensions never cross implicitly; tiny nonzero requirements cannot round into free ingredients.

Testing steps: Run validation/quantity tests, including booleans, NaN/infinity, zero, incompatible units, impossible dates and tiny amounts.

Evidence: `1bf7f6e`; models and `services/quantities.py`. This does not authorize additional guessed conversions.

### FF-09 - Exclude expired stock from calculations and handle expiry urgency

**MVP — Completed | P0 | Dependencies: FF-07, FF-08**

MVP scope basis: Sections 3.1-3.2 and acceptance criteria 2-3: expired-stock exclusion and urgency.

Description: Keep expired stock visible but unusable and rank eligible near-expiry ingredients appropriately.

Acceptance criteria: Matching, substitutions, shopping and cooking use zero expired stock; today through day three is inclusive by default; urgency is not a food-safety guarantee.

Testing steps: Run `test_calculations.py` and inventory tests with yesterday/today/day-three/day-four dates; compare every availability calculation.

Evidence: `1bf7f6e`, `b54a99a`; `stock`, `summary`, dashboard tests. Non-default threshold presentation remains FF-39.

### FF-10 - Deliver pantry cards, search, filters and edit forms

**MVP — Completed | P1 | Dependencies: FF-03, FF-07, FF-08, FF-09**

MVP scope basis: Section 3.1 and section 4: pantry browsing/filtering, forms and basic states.

Description: Browse and manage pantry inventory through the established frontend.

Acceptance criteria: Ingredient search, category/expiry filters, quantities/dates, compatible-unit forms and CRUD controls exist; loading/empty/error states are present.

Testing steps: Run domain/routing/HTTP integration tests; reproduce recorded browser CRUD; inspect filter predicates in `routes/pantry.tsx`.

Evidence: `a053f16`, `a507929`, `docs/integration.md`. Filters are code-reviewed; comprehensive pantry component automation is not claimed. Inline server feedback remains FF-42.

### FF-11 - Deliver desktop navigation and responsive application shell

**MVP — Completed | P1 | Dependencies: FF-01, FF-03**

MVP scope basis: Sections 1 and 4: five destinations, desktop sidebar and responsive collapse.

Description: Expose Dashboard, Pantry, Recipes, Basket and Shopping List with sidebar and compact-screen menu.

Acceptance criteria: All destinations resolve; responsive toggle/menu-close behavior is implemented; existing visual identity remains intact.

Testing steps: Run `src/test/app-routing.test.tsx`; inspect `AppShell.tsx` responsive classes and reproduce documented desktop navigation.

Evidence: Existing frontend retained in `16ec563`, navigation completed in `a053f16`. Narrow-screen/keyboard acceptance is still FF-46; routing tests do not prove mobile interaction.

## M2 - Recipes and supported live import

### FF-12 - Fetch real TheMealDB candidates through the backend

**MVP — Completed | P1 | Dependencies: FF-05**

MVP scope basis: Section 3.2: real backend TheMealDB discovery and source error handling.

Description: Traverse first-letter searches per import, deduplicate IDs and handle upstream failures.

Acceptance criteria: Response shape is validated; timeouts and TLS verification are enabled; failures become `SOURCE_UNAVAILABLE`; page reads do not import.

Testing steps: Run source-adapter/failure tests in `test_importer.py`; verify mocked letter traversal, malformed payload rejection and deduplication; inspect timeout/TLS setup.

Evidence: `1bf7f6e`; `TheMealDBSource`. Adapter mechanics are separate from source sufficiency in FF-18 to FF-21.

### FF-13 - Reject unquantified recipes and normalize exact supported measures

**MVP — Completed | P0 | Dependencies: FF-06, FF-08, FF-12**

MVP scope basis: Section 3.2 and acceptance criterion 5: quantified supported recipes with no guessed measures.

Description: Accept only supported identities and confidently quantified lines with complete metadata.

Acceptance criteria: Exact fractions work; repeated identities aggregate; unsupported names, ranges, undefined cups, packages, pinches and to-taste measures are rejected with reasons; no ingredient line silently disappears.

Testing steps: Run exact/ambiguous quantity and captured-source cases in `test_importer.py`; compare normalized output with raw fixture lines.

Evidence: `1bf7f6e`; `normalize_meal`, `parse_measure`, two real captured responses. This does not prove 15 accepted real recipes.

### FF-14 - Upsert source recipes idempotently and report import outcomes

**MVP — Completed | P0 | Dependencies: FF-12, FF-13**

MVP scope basis: Section 3.2 and acceptance criterion 4: idempotent import, rejection reports and preserved prior data.

Description: Support startup/explicit import with stable external-ID upserts and no partial changes after source failure.

Acceptance criteria: Duplicate IDs update existing records/references; accepted distinct records cap at 20; imported/updated/skipped totals are correct; failed traversal preserves previous data.

Testing steps: Run importer idempotence, cap, failure and restart-upsert tests; compare recipe IDs and references before/after import.

Evidence: `1bf7f6e`, `b54a99a`; unique `external_id` and import transaction. Synthetic 20-record tests do not satisfy the live minimum.

### FF-15 - Search, filter and rank backend recipe discovery

**MVP — Completed | P1 | Dependencies: FF-09, FF-14**

MVP scope basis: Section 3.2 and acceptance criterion 3: discovery/search, match percentage and ranking.

Description: Display recipe images/categories, original-line match scores and expiry notes with title/category filters and sorting.

Acceptance criteria: Score is rounded adequately-covered/total lines at base scale; urgency breaks ties; unapproved substitutions cannot inflate score; match/title sort works.

Testing steps: Run matching/search/urgency calculations and HTTP integration; reproduce recorded recipe discovery and inspect `recipes.index.tsx`.

Evidence: `1bf7f6e`, `a053f16`, `a507929`. Real recipe variety remains dependent on open corpus work.

### FF-16 - Show recipe details and scale canonical demands consistently

**MVP — Completed | P0 | Dependencies: FF-08, FF-15**

MVP scope basis: Section 3.3 and acceptance criterion 6: detail and consistent requested/base scaling.

Description: Return instructions/image/base metadata, scaled requirements and expiry-aware stock for a selection.

Acceptance criteria: Requested numeric scale is integer 1-8; every demand uses requested/base; detail, shopping and cooking share the same calculation.

Testing steps: Run base-servings scaling/shared-demand tests; request multiple scales through the HTTP adapter and compare exact amounts.

Evidence: `1bf7f6e`, `a053f16`, `a507929`; `demands` and recipe detail UI. Numeric scaling is complete; human-portion semantics remain FF-38.

### FF-17 - Suggest eligible substitutions and require explicit confirmation

**MVP — Completed | P0 | Dependencies: FF-06, FF-09, FF-16**

MVP scope basis: Section 3.3 and acceptance criterion 6: reviewed eligible substitutions with explicit confirmation.

Description: Apply ten reviewed category-limited rules with ratios/explanations only after user confirmation.

Acceptance criteria: Suggestions require compatible units and enough aggregate usable substitute stock; duplicate/wrong-context/invalid choices fail; confirm/reject/undo controls exist; saved basket choices affect demands.

Testing steps: Run substitution calculations and frontend domain/mock tests; reproduce confirmation/undo in detail and basket.

Evidence: `1bf7f6e`, `a053f16`, `a507929`; rules/category eligibility and choice validation. Restoring saved choices in recipe detail remains FF-40.

### FF-18 - Audit live candidate feasibility for 15-20 strictly supported recipes

**MVP — Remaining | Readiness: ready | P0 | Dependencies: FF-12, FF-13 | Parallel lane A | Estimate: 2-4 hours**

MVP scope basis: Section 3.2 and acceptance criteria 4-5: evidence needed to resolve the mandatory real-source count without relaxing normalization.

Description: Replace the historical one-of-790 result with a reproducible current candidate/rejection audit. Inspect every line of promising recipes, not just the first rejection, before choosing a mapping strategy.

Acceptance criteria: Record fetch date, real source IDs and rejection categories. Produce a candidate matrix showing how at least 15 distinct recipes could qualify using exact existing or evidence-backed mappings. Identify genuinely unavailable conversions and yields. If fewer than 15 are supportable, document the shortfall and source/spec decision needed; the production requirement stays blocked, not waived.

Testing steps: Fetch through the existing adapter without changing the production pantry/database; retain raw audit payloads; run the strict normalizer and independently inspect proposed candidates. Distinguish source failure from normalization rejection.

Evidence/gap: No committed 15-recipe valid real corpus exists. Synthetic import tests are not a replacement. Parallel opportunity: independent of all frontend corrections and offline startup checks.

### FF-19 - Implement reviewed identities and exact measures for the supported subset

**MVP — Remaining | Readiness: blocked by FF-18 | P0 | Dependencies: FF-18 | Parallel lane A | Estimate: 4-10 hours, conditional on feasibility**

MVP scope basis: Section 3.2 and acceptance criteria 4-5: exact reviewed mappings needed for the supported subset.

Description: Support the smallest real-source subset that reaches the target through documented identity equivalence and exact conversion rules, preserving strict rejection.

Acceptance criteria: Each mapping has an explicit basis and applicability; every accepted recipe line is accounted for. No guessed density, portion mass, package size, omitted garnish or hand-entered recipe. Maintain the small catalog and stable IDs/units; do not reinterpret saved inventory. Any necessary canonical-unit/schema change needs an explicit migration design before implementation. If exact mappings cannot deliver 15 recipes, leave the target blocked and escalate the source/spec conflict.

Testing steps: Add positive and near-miss rejection cases per mapping, including different identities and incompatible dimensions. Run importer/inventory/persistence tests against fresh and existing SQLite data.

Parallel opportunity: isolate catalog/importer changes from frontend work. This is one coherent mapping implementation issue, not one issue per recipe or ingredient.

### FF-20 - Establish a provenance-backed regression corpus of 15-20 real recipes

**MVP — Remaining | Readiness: blocked by FF-19 | P0 | Dependencies: FF-18, FF-19 | Lane A; fixture review can overlap | Estimate: 2-4 hours**

MVP scope basis: Sections 3.2 and 7 (criteria 4-6, 8, 11, 13): source-backed normalization and arithmetic regression evidence.

Description: Make the support claim reproducible offline with unaltered TheMealDB payloads passed through the actual normalizer.

Acceptance criteria: Preserve IDs, capture dates and provenance for 15-20 accepted recipes; assert metadata and normalized identities/amounts. Include representative rejected records to prevent permissive regressions. Fixtures are source evidence, not synthetic production fallback seeds. Exercise at least one supported-source recipe through shopping and cooking arithmetic.

Testing steps: Normalize/import the full corpus offline, repeat import, compare counts/stable IDs, and independently check expected amounts against raw measures rather than computing expectations with the same parser.

Evidence/gap: Only two real raw fixtures are currently committed; the frontend's larger mock seed is not evidence of live support. Parallel opportunity: a reviewer can prepare captured fixtures after candidate selection, before implementation finishes.

### FF-21 - Verify production startup imports 15-20 real recipes and re-imports safely

**MVP — Remaining | Readiness: blocked by FF-20 | P0 | Dependencies: FF-14, FF-20, FF-32, FF-33 | Lane A | Estimate: 1-2 hours**

MVP scope basis: Sections 2, 3.2 and acceptance criterion 4: automatic real-source seed, 15-20 recipes and stable repeat import.

Description: Prove the normal startup/import path reaches the target in a fresh SQLite database with real connectivity.

Acceptance criteria: Record startup and explicit import reports with 15-20 unique valid source IDs and complete instructions/category/image/ingredients. Re-import creates no duplicates. Restart at the same URL retains records/references. Report upstream changes/failures honestly; do not satisfy the count with manually composed or synthetic records.

Testing steps: Run the normal app using a temporary file-backed `DATABASE_URL`; query recipes, re-import, inspect SQLite counts/foreign keys, restart and compare normalized records. Retain evidence for FF-44/FF-47.

Parallel opportunity: execute after corpus verification; other work should not wait on live connectivity.

## M3 - Basket, shopping and cooking

### FF-22 - Implement duplicate-free basket selections with stored choices

**MVP — Completed | P0 | Dependencies: FF-16, FF-17**

MVP scope basis: Section 3.4 and acceptance criteria 6-7: unique basket selections and stored choices.

Description: Add/update/remove recipe selections with per-item scale and confirmed substitutions.

Acceptance criteria: Re-adding updates scale instead of duplicating; omitted patch fields stay unchanged; clearing choices is explicit; selected substitutions affect aggregate demands.

Testing steps: Run basket upsert/substitution calculations and persistence tests; re-add at another scale and compare IDs, choices and totals.

Evidence: `1bf7f6e`, `b54a99a`; basket router/service, unique recipe constraint, substitutions JSON. Storage mechanics are documented in M4 rather than treated as missing here.

### FF-23 - Deliver basket selection editing and cumulative requirements

**MVP — Completed | P1 | Dependencies: FF-11, FF-22**

MVP scope basis: Section 3.4: editable selections and cumulative ingredient requirements.

Description: Render saved recipes, scale controls, substitute choices, removal, cumulative ingredients and shopping/cooking entry points.

Acceptance criteria: Controls call the shared service; quantities refresh after confirmed changes; loading/error/empty states exist.

Testing steps: Run `src/test/basket-shopping.test.tsx` and HTTP integration; compare cumulative quantities with backend results after changing scale.

Evidence: `a053f16`, `a507929`; `routes/basket.tsx` and recorded browser journey. Reusing choices in recipe detail remains FF-40.

### FF-24 - Aggregate grocery requirements and subtract pantry stock once

**MVP — Completed | P0 | Dependencies: FF-09, FF-22**

MVP scope basis: Section 3.5 and acceptance criterion 8: aggregate requirements and subtract pantry once.

Description: Combine canonical basket requirements after applying confirmed substitutions.

Acceptance criteria: Shared ingredients aggregate; usable stock subtracts once; to-buy is clamped at zero; expired stock and incompatible dimensions cannot contribute.

Testing steps: Run shared-pasta, g/kg, ml/l and substituted shopping cases in backend calculations and frontend domain/HTTP tests; assert exact quantities.

Evidence: `1bf7f6e`, `a053f16`; `aggregate`, `basket_demands`, `generate_shopping`.

### FF-25 - Preserve shopping edits and require confirmation before regeneration

**MVP — Completed | P0 | Dependencies: FF-24**

MVP scope basis: Section 3.5 and acceptance criterion 9: preserve manual edits and confirm destructive regeneration.

Description: Maintain manual/generated lines, overrides, removal and purchased status through explicit regeneration.

Acceptance criteria: Regeneration resets generated lines and preserves manual ones unless reset is chosen; edited/purchased/removed generated lines or destructive manual reset require `force` confirmation.

Testing steps: Run regeneration and frontend overwrite tests; remove a generated line, reopen the database and verify confirmation remains required.

Evidence: `1bf7f6e`, `a053f16`, `b54a99a`; saved `edited` and `removed_generated` markers with restart coverage.

### FF-26 - Deliver shopping forms and explicit received-purchase confirmation

**MVP — Completed | P1 | Dependencies: FF-23, FF-25**

MVP scope basis: Sections 3.5 and 4: explicit received quantity/date and confirmed purchase feedback.

Description: Render shopping lines and confirm actual quantity/expiry before transfer into pantry.

Acceptance criteria: Checking purchased alone changes no pantry stock; catalog-linked lines expose confirmation fields; transfer completion appears only after service success; failed transfer stays recoverable.

Testing steps: Run all five `basket-shopping.test.tsx` cases, especially deferred confirmation and failed transfer; reproduce the recorded purchase journey.

Evidence: `a053f16`, `a507929`; `routes/shopping.tsx`. Feedback improvements in other shopping forms remain FF-42.

### FF-27 - Transfer purchases atomically and exactly once

**MVP — Completed | P0 | Dependencies: FF-07, FF-25**

MVP scope basis: Section 3.5 and acceptance criterion 10: atomic exactly-once transfer.

Description: Merge confirmed purchased stock and its completion marker within one inventory transaction.

Acceptance criteria: Catalog linkage, purchased status, quantity and expiry are validated; differing expiry conflicts without changes; retries/concurrency cannot double-add; completion cannot be unchecked.

Testing steps: Run transfer cases in `test_inventory_transactions.py` and durable write-failure/restart/independent-engine tests in `test_persistence.py`.

Evidence: `1bf7f6e`, `b54a99a`; marker and pantry merge share a SQLite transaction. Independent connection tests do not claim multi-machine cloud-sync support.

### FF-28 - Revalidate cooking and atomically deduct stock with history

**MVP — Completed | P0 | Dependencies: FF-09, FF-16, FF-17**

MVP scope basis: Section 3.6 and acceptance criterion 11: preview, shortage blocking and atomic deductions/history.

Description: Preview aggregate deductions, then validate current stock again at confirmation.

Acceptance criteria: Any shortage blocks every deduction; scaled/substituted demands aggregate correctly; depleted entries are removed; history and deductions commit together or neither commits.

Testing steps: Run stale-preview, shared-substitute, failure-injection and competing-cook cases; reopen the database after SQL failure to check durable rollback.

Evidence: `1bf7f6e`, `b54a99a`; `preview`, `confirm_cook`, inventory/persistence tests. Cooking is intentionally non-idempotent; uncertain UI outcomes remain FF-41.

### FF-29 - Deliver cooking preview and confirmation from detail and basket

**MVP — Completed | P1 | Dependencies: FF-23, FF-28**

MVP scope basis: Section 3.6 and section 4: cooking entry points, deduction preview and truthful success feedback.

Description: Show the selected request's deductions and block confirmation while previewing or short of stock.

Acceptance criteria: Required/available amounts and substitutes are displayed; only confirmed success toasts and refreshes views; both entry points use selected scale/choices.

Testing steps: Reproduce documented blocked/successful cooking; run the HTTP journey; inspect preview cancellation and confirmation disabled states in `CookDialog.tsx`.

Evidence: Component refined in `a053f16` and `a507929`; historical browser evidence. This closes success/blocked paths, not stale/error recovery in FF-41.

### FF-30 - Provide persisted history and dashboard recommendations through the API

**MVP — Completed | P1 | Dependencies: FF-15, FF-28**

MVP scope basis: Sections 3.6-3.7 and 5: stored history, dashboard counts/recommendations/recent records.

Description: Store recipe/time/scale/consumption snapshots; return full history plus dashboard counts, recommendations and recent records.

Acceptance criteria: History is newest-first; dashboard contains pantry/soon/expired counts, up to four recommendations and five recent records; no speculative analytics.

Testing steps: Run contract/calculation/persistence tests; cook and verify history/dashboard fields and restart retention; inspect Dashboard presentation.

Evidence: `1bf7f6e`, `a053f16`, `b54a99a`. API returns full history, Dashboard only five recent entries; reaching older records in UI remains FF-43.

### FF-31 - Connect production services to HTTP with recoverable transport errors

**MVP — Completed | P1 | Dependencies: FF-03, FF-04, FF-05**

MVP scope basis: Sections 1-2 and 4: real centralized HTTP service, CORS and recoverable failures.

Description: Use the HTTP adapter by default, configurable API origin and local Vite CORS.

Acceptance criteria: All 23 calls preserve quantities/messages and contract encoding; IDs/substitutions encode safely; empty deletes work; errors are recoverable `ServiceError`; no mock fallback on failure.

Testing steps: Run HTTP unit/integration suites, typecheck and API validation; test allowed/disallowed CORS preflights.

Evidence: `a507929`; adapter/hooks, `frontend/.env.example`, backend CORS. This is transport implementation; FF-36 accounts for integration evidence.

## M4 - Durable storage and integration

### FF-32 - Persist the specification model with SQLAlchemy and SQLite

**MVP — Completed | P0 | Dependencies: FF-05, FF-06, FF-14, FF-22, FF-25, FF-30**

MVP scope basis: Sections 2 and 5: SQLAlchemy/SQLite schema, configurable URL and persisted entities.

Description: Replace authoritative process dictionaries with a relational SQLite unit of work configured by `DATABASE_URL`.

Acceptance criteria: All eight spec tables and internal settings exist; references/numeric canonical columns persist; basket/history JSON preserves API shapes; uniqueness and nonnegative inventory constraints are enforced.

Testing steps: Run `test_persistence.py`, inspect tables/foreign keys and a custom file URL, and rerun unchanged response-schema tests.

Evidence: `b54a99a`; SQLAlchemy Core tables in `app/store.py` and transaction-local state. No PostgreSQL/Docker/authentication was introduced.

### FF-33 - Initialize database and sample seeds without duplicates

**MVP — Completed | P1 | Dependencies: FF-32**

MVP scope basis: Sections 2, 3.2 and 5: repeat-safe initialization and seeds that preserve user data.

Description: Create schema/catalog/rules idempotently and seed example pantry only once.

Acceptance criteria: Repeated starts retain 40 ingredient/10 rule rows; recipe external IDs stay stable; an emptied pantry does not repopulate on restart.

Testing steps: Run `test_seed_is_unique_and_deleted_pantry_stays_deleted` and import restart cases; inspect counts after repeated store creation.

Evidence: `b54a99a`; conflict-safe inserts and persistent `pantry_seeded` marker. Seed mechanism is complete, while 15 supported real recipe seeds remain FF-21.

### FF-34 - Prove durable rollback and serialize competing inventory operations

**MVP — Completed | P0 | Dependencies: FF-27, FF-28, FF-32**

MVP scope basis: Sections 3.5-3.6, 5 and acceptance criteria 10-11, 13: durable transaction/inventory evidence.

Description: Protect inventory through real SQL transactions, not just memory rollback or a process lock.

Acceptance criteria: Failure after pantry SQL writes rolls back history/transfer markers; six independent engines cannot overcook or double-transfer; constraints reject negative/duplicate stock.

Testing steps: Run parametrized write-failure/independent-engine/constraint tests and existing threaded inventory tests; reopen file to verify durable rollback.

Evidence: `b54a99a`; `BEGIN IMMEDIATE`, transaction context, explicit SQL failure injection. No crash/power-loss experiment is claimed.

### FF-35 - Prove state survives a new Python process opening the same database

**MVP — Completed | P0 | Dependencies: FF-32, FF-33, FF-34**

MVP scope basis: Section 2 and acceptance criteria 1, 7, 10-11: process-restart persistence evidence.

Description: Reopen durable application state with a separate interpreter.

Acceptance criteria: Pantry/expiry, recipes, basket choices, shopping manual/edit/transfer state, history and removed-generated protection survive; transfer retry after reopening adds nothing.

Testing steps: Run `test_all_entities_survive_a_new_python_process` and restart import cases; compare serialized state, not only counts.

Evidence: `b54a99a`; subprocess persistence tests. Synthetic source and service-level process checks are not a full live browser restart journey; see FF-44.

### FF-36 - Verify every service operation through the actual HTTP adapter

**MVP — Completed | P0 | Dependencies: FF-31, FF-32, FF-34**

MVP scope basis: Section 2 and acceptance criteria 12-13: real frontend/API integration verification.

Description: Start isolated FastAPI on a free port and exercise production TypeScript calls.

Acceptance criteria: Every operation, CORS, validation, units, expiry, substitutions, regeneration, purchase and cooking are exercised; fixture data cannot touch the developer database.

Testing steps: Run `npm test -- src/services/httpService.integration.test.ts`; inspect file-backed temporary database and synthetic strict source in `backend/tests/http_server.py`.

Evidence: `a507929`, `b54a99a`; both integration cases passed in the original backlog verification. This does not establish the real recipe minimum.

### FF-37 - Document local startup, API configuration and initial SQLite setup

**MVP — Completed | P1 | Dependencies: FF-02, FF-31, FF-32, FF-35**

MVP scope basis: Section 2 step 7: local startup, setup and verification documentation.

Description: Document uv/npm startup, API origin/CORS, database URL/schema/seeds/backups and verification.

Acceptance criteria: Instructions explain automatic initial tables, persistence, one-time seeds, absent migration from lost memory/mock data and live import limitations honestly.

Testing steps: Compare README commands with scripts/env reads; reproduce startup against isolated new/existing databases. Current tests and preceding build support the documented toolchain.

Evidence: `1bf7f6e`, `a507929`, `b54a99a`; READMEs/integration notes. Final acceptance results and stale explanatory prose are FF-47.

## M5 - MVP acceptance gaps and sign-off

### FF-38 - Resolve recipe yield semantics and misleading serving labels

**MVP — Remaining | Readiness: ready; source evidence may block closure | P1 | Dependencies: FF-16; coordinate FF-18 | Parallel lane B | Estimate: 1-3 hours, excluding unavailable source evidence**

MVP scope basis: Section 3.3 and acceptance criterion 6: accurate base-serving meaning and consistent scaling; guessing yield is prohibited.

Description: Import assigns `base_servings=1` to a whole source batch because TheMealDB lacks yield data, while detail/basket/dialog/history call it a human serving. README disclosure alone does not correct the in-app promise.

Acceptance criteria: Establish a consistent, evidence-backed meaning of base/requested servings. Prefer verified yields when available; never infer portions. If whole-batch scaling stays, label it clearly throughout and record that accepting this interpretation of the spec's serving requirement needs an explicit product decision. Text changes alone do not establish literal yield compliance. Preserve numeric API shapes and 1-8 constraints.

Testing steps: Compare raw quantities/yield evidence with detail, basket, shopping, preview and history at two scales; add copy tests and retain scaling tests. Record unresolved interpretation as a release exception, not completion.

Parallel opportunity: investigate copy independently of mappings; final meaning must agree with the supported corpus. No speculative yield-collection feature is requested.

### FF-39 - Align configurable expiry thresholds in backend and frontend

**MVP — Remaining | Readiness: ready | P1 | Dependencies: FF-09, FF-10, FF-30 | Lane B | Estimate: 1-2 hours**

MVP scope basis: Section 3.1 and acceptance criteria 2-3: configurable expiry highlighting consistent with backend calculations.

Description: Backend reads `FRESHFIRST_EXPIRY_DAYS`, but frontend `EXPIRY_THRESHOLD_DAYS`, dashboard labels and detail notes hardcode three. Non-default configuration can show contradictory states and recommendations.

Acceptance criteria: Use/document coordinated launch/build configuration with default three and valid nonnegative integers. Pantry status/filtering, counts and numeric notes agree. Avoid a new API endpoint/schema or settings product just to carry this configuration; remove misleading fixed numeric prose where appropriate.

Testing steps: Run with thresholds three and five using day-four/five/six items; compare pantry filters, dashboard and recipe notes/ranking. Test invalid/negative configuration and expiry boundaries.

Parallel opportunity: independent of importer; coordinate recipe-detail copy with FF-38.

### FF-40 - Preserve saved basket choices when editing through recipe details

**MVP — Remaining | Readiness: ready | P1 | Dependencies: FF-17, FF-22, FF-23 | Lane B | Estimate: 1-3 hours**

MVP scope basis: Sections 3.3-3.4 and acceptance criteria 6-7, 12: preserve confirmed selection state and recover from partial actions.

Description: Detail initializes local scale/choices from defaults, uses the saved item mainly for its update label, and performs add/upsert followed by a substitution patch. Reopening can clear prior choices; failure of the second call can leave the first mutation saved.

Acceptance criteria: Load saved choices explicitly when editing a selection, and do not overwrite them without user action. Existing items use the existing patch for coordinated changes. Handle any unavoidable new-item multi-call partial failure visibly and reconcile server state; do not claim contract-level atomicity. Changing recipe identity cannot retain another recipe's local choices.

Testing steps: Save nondefault scale/substitutions, reopen, change only scale, simulate patch failure after add, navigate to another recipe and reload. Assert correct feedback, choices and totals with focused UI/service tests.

Parallel opportunity: independent of source work; one owner should coordinate FF-38 and this issue's `recipes.$id.tsx` edits.

### FF-41 - Recover cooking UI after stale stock or uncertain confirmation outcome

**MVP — Remaining | Readiness: ready | P1 | Dependencies: FF-28, FF-29, FF-31 | Lane B | Estimate: 1-2 hours**

MVP scope basis: Sections 3.6 and 4 and acceptance criteria 11-12: recoverable truthful cooking outcomes without automatic duplicate deductions.

Description: `CookDialog.confirm` invalidates queries after success only; its catch path merely toasts. A 409 or lost response can leave stale preview/inventory/history. Cooking is explicitly non-idempotent.

Acceptance criteria: Failed confirmation reconciles affected views and invalidates/reloads preview; preview failure offers a useful retry. A transport failure after submission explains that the outcome may require checking; never automatically retry a non-idempotent cook. Pending/error UI cannot imply an unconfirmed deduction.

Testing steps: Change inventory after preview and return 409; fail/retry preview; commit server-side then drop confirmation response. Verify refreshed history, no automatic duplicate confirmation and preserved successful flow.

Parallel opportunity: isolated component work can overlap importer or pantry/shopping forms; coordinate any shared hook edits.

### FF-42 - Complete inline validation and recoverable form mutation feedback

**MVP — Remaining | Readiness: ready | P1 | Dependencies: FF-10, FF-26, FF-31 | Lane B | Estimate: 1-2 hours**

MVP scope basis: Section 4 and acceptance criterion 12: inline validation and recoverable errors are required UX, not polish.

Description: Pantry has local field errors, but API save conflicts are toast-only; shopping overrides similarly rely on native constraints/toasts. Spec section 4 asks for inline validation and recoverable errors too.

Acceptance criteria: Pantry and shopping forms retain input on backend rejection and show actionable inline quantity/date/expiry-conflict messages. Keep notifications and existing design. Blank/nonfinite values cannot produce false success; pending actions are disabled appropriately.

Testing steps: Use deferred/rejected services, submit invalid values and `EXPIRY_CONFLICT`, correct in place and resubmit. Assert visible errors, retained values, unchanged stock on failure and exactly one confirmed success.

Parallel opportunity: independent of Lane A/CookDialog. This is one bounded feedback improvement, not a separate issue for every field.

### FF-43 - Make the complete persisted cooking history reachable in the UI

**MVP — Remaining | Readiness: ready | P1 | Dependencies: FF-30, FF-31, FF-35 | Lane B | Estimate: 1-2 hours**

MVP scope basis: Section 3.6: reachable simple cooking history; section 3.7 recent history alone does not expose older records.

Description: `listHistory` and `useHistory` exist, but no rendered view uses them; Dashboard receives only five recent records. Older saved records have no user-facing entry point despite the simple history requirement.

Acceptance criteria: Provide a simple complete list, for example an expansion within Dashboard, using the existing service and design. Show recipe/date/selected scale with correct order and loading/empty/error states. No analytics, new sidebar section or API is needed.

Testing steps: Create six or more records, reach the sixth after refresh/backend restart, and verify newest-first ordering and error/empty behavior. Do not redo already implemented history storage/API.

Parallel opportunity: largely Dashboard-local; agree serving labels with FF-38.

### FF-44 - Execute the live-recipe browser journey through SQLite restart

**MVP — Remaining | Readiness: blocked by corpus and required UX fixes | P0 | Dependencies: FF-21, FF-35, FF-36, FF-38 to FF-43 | Parallel lane C | Estimate: 2-3 hours**

MVP scope basis: Section 7 criterion 13, supported by criteria 1-12: full user-flow and restart acceptance.

Description: Close spec acceptance criterion 13 with real supported recipes, browser interaction and durable backend restart. Existing evidence covers synthetic browser integration plus separate automated persistence, not this combined run.

Acceptance criteria: Record Pantry -> Recipes -> Basket -> Shopping -> Purchase -> Cook -> Restart. Include two recipes with shared stock, scaling, explicit substitution where supported context permits, expired-stock exclusion, manual edit protection and exact deductions/history. Browser reload/backend restart retain choices/transfer flags/history. Capture source IDs and dates. If a real subset cannot exercise a reviewed rule, identify a strict-fixture supplement separately rather than claiming a live substitution check occurred.

Testing steps: Drive existing UI against normal FastAPI and a temporary SQLite file with real import. Retain before/after API/database snapshots, restart the same URL, retry completed transfer and prove no double addition. Document actual failures before declaring pass.

Parallel opportunity: prepare checklist and snapshots now; final execution waits for dependencies. A new permanent browser-test platform is unnecessary.

### FF-45 - Verify offline restart and failed startup import preserve saved data

**MVP — Remaining | Readiness: ready, verification only | P1 | Dependencies: FF-14, FF-32, FF-35 | Lane C | Estimate: 1-2 hours**

MVP scope basis: Section 3.2: previously imported data must remain usable when the external source is unavailable.

Description: Source-failure and process-persistence tests pass separately; production lifespan with an existing file plus unavailable upstream lacks explicit combined acceptance evidence.

Acceptance criteria: Reopening an existing file with injected startup timeout/malformed source preserves and serves recipes, pantry, basket, shopping and history. Failure is logged without data replacement/reseeding. An initially empty offline database remains honest about absent recipes and recovers through explicit import later.

Testing steps: Start another app/lifespan on a saved file with a deterministic failing source, query and compare snapshots; repeat on an empty file followed by successful retry. Inject bounded failure instead of depending on a live outage.

Parallel opportunity: independent of corpus and frontend changes; perform while FF-18 investigates feasibility. This issue verifies a claimed behavior, not a confirmed data-loss bug.

### FF-46 - Verify mobile navigation, keyboard forms and confirmation usability

**MVP — Remaining | Readiness: ready, verification and reproduced fixes only | P1 | Dependencies: FF-11, FF-23, FF-26, FF-29; final rerun after FF-38 to FF-43 | Lane C | Estimate: 1-2 hours**

MVP scope basis: Sections 1 and 4: functional responsive navigation/forms/confirmations; no broad certification requirement.

Description: Responsive implementation exists, but current evidence does not cover narrow-screen interaction, keyboard focus or long import reports.

Acceptance criteria: At desktop and representative 375px width, all destinations are reachable; key forms and overwrite/cook confirmations work by keyboard; content stays readable; a long skip report remains usable in the viewport. Fix only reproduced failures; preserve design and avoid expanding into a broad accessibility certification project.

Testing steps: Tab through navigation, pantry fields, substitutions, actual purchase/date, regeneration and cooking. Check cancellation/focus return, overflow and slow/error states; record browser/viewport/results.

Parallel opportunity: inspect stable screens now; coordinate dialog/form fixes with FF-41/FF-42 and rerun affected interactions afterward.

### FF-47 - Update repository docs with accurate final setup and acceptance evidence

**MVP — Remaining | Readiness: blocked on acceptance results | P1 | Dependencies: FF-44, FF-45, FF-46 | Lane C | Estimate: 0.5-1 hour**

MVP scope basis: Section 2 step 7 and section 7: accurate startup documentation and recorded final verification.

Description: Finalize current-state documentation without erasing history. OpenAPI prose still says no HTTP client/backend exists; historical integration sections describe restart data loss.

Acceptance criteria: Include actual source count/IDs, configuration/serving meaning, browser-restart results, warnings and unresolved exceptions. Update misleading OpenAPI explanatory prose only, preserving paths, IDs, schemas, response codes and security. Clearly label historical sections and never claim unrun tests passed.

Testing steps: Follow startup in a clean checkout; validate API coverage; compare structural contract fields before/after prose edits; trace completion claims to captured evidence.

Parallel opportunity: draft corrections early, finalize results after acceptance checks. This updates final release evidence, distinct from the already delivered initial setup instructions in FF-37.

### FF-48 - Run the final regression gate and decide v1.0 acceptance

**MVP — Remaining | Readiness: blocked on remaining issue closure | P0 | Dependencies: FF-47 (transitively all remaining MVP gates) | Integration owner | Estimate: 0.5-1 hour**

MVP scope basis: Section 7: evidence-backed MVP acceptance across every required criterion.

Description: Decide readiness using all spec acceptance criteria rather than the issue count or a single green command.

Acceptance criteria: Every acceptance criterion has evidence; every remaining MVP issue meets its acceptance criteria, including a documented serving interpretation consistent with the specification. A waiver or reduction of a mandatory requirement is not MVP completion under this unchanged specification. The 15-20 real-recipe target is met or v1.0 stays blocked. No invented records, permissive conversions or extra features appear. Preserve the API and stored data; commit final changes without rewriting history.

Testing steps: Run locked dependency setup, backend pytest/Ruff/format, frontend tests/typecheck/API validation/lint/build; review FF-44 to FF-46 evidence and final diff. Record actual results/warnings. This verification does not authorize issue creation, publishing, deployment or release tagging.

Parallel opportunity: this is the join point; run the final gate after the changes it validates.

## Specification acceptance coverage

| Spec section 7 criterion | Implemented evidence | Remaining acceptance work |
| --- | --- | --- |
| 1. Pantry survives refresh/restart | FF-07, FF-35, FF-36 | FF-44 combines browser/backend restart |
| 2. Expired stock excluded everywhere | FF-09, FF-24, FF-28 | FF-39 non-default UI; FF-44 live journey |
| 3. Meaningful matching and urgency | FF-15 | FF-39, FF-44 |
| 4. 15-20 normalized unique real recipes | FF-12 to FF-14 mechanics only | **FF-18 to FF-21 remain blocking** |
| 5. Ambiguous measures rejected | FF-08, FF-13 | FF-19/FF-20 must preserve rejection |
| 6. Scaling and explicit substitution | FF-16, FF-17, FF-22 | FF-38 meaning; FF-40 saved detail choices |
| 7. Persistent basket | FF-22, FF-35 | FF-40, FF-44 |
| 8. Shared groceries / compatible units | FF-08, FF-24 | FF-20 real-source arithmetic; FF-44 |
| 9. Manual shopping edits retained | FF-25, FF-35 | FF-42 feedback; FF-44 |
| 10. Exactly-once purchase transfer | FF-27, FF-34, FF-35 | FF-44 browser restart |
| 11. Atomic cooking/history | FF-28, FF-34 | FF-41 reconciliation; FF-44 |
| 12. Recoverable errors/no false success | FF-05, FF-26, FF-31, FF-36 | FF-40, FF-41, FF-42, FF-45 |
| 13. Tests plus complete manual journey | FF-34 to FF-36; historical synthetic browser run | FF-44, FF-45, FF-46, FF-48 |

Additional section 3/4 coverage: FF-43 exposes full simple history; FF-46 completes responsive/keyboard validation. Neither introduces a feature outside the specified scope.

## Critical blockers and fastest execution order

### Minimum release dependency chain

**FF-18 -> FF-19 -> FF-20 -> FF-21 -> FF-44 -> FF-47 -> FF-48** is the expected longest serial branch. Existing completed milestones are prerequisites already delivered, not work to redo.

| Serial segment | Required outcome | Base effort |
| --- | --- | --- |
| FF-18 | Current source feasibility evidence | 2-4 hours |
| FF-19 | Only necessary exact identity/measure support | 4-10 hours |
| FF-20 | Real-source corpus and regression evidence | 2-4 hours |
| FF-21 | Normal production startup/re-import count and persistence | 1-2 hours |
| FF-44 | Complete browser journey and backend restart acceptance | 2-3 hours |
| FF-47 | Accurate final documentation | 0.5-1 hour |
| FF-48 | Final regression and sign-off | 0.5-1 hour |
| Expected serial critical path | Seven existing issues | **12-25 hours before contingency** |

The figure is sequential engineering time, not the total effort for all remaining MVP work or a guaranteed delivery date. Budget approximately **15-32 hours with critical-path contingency**, assuming exact mappings are feasible and parallel required branches are ready at the joins. With one contributor doing all tasks, use the full 20-43-hour base / 25-55-hour planning estimate below instead.

The following work is **mandatory off the expected source critical path**, not Post-MVP:

- **Frontend branch FF-38 to FF-43:** 6-14 hours of effort; start immediately. These issues join before FF-44. Resolve source-dependent serving semantics while FF-18/FF-19 run; coordinate shared detail/history edits. If this branch or its yield decision finishes later, it becomes the actual limiting branch and delays the join.
- **Offline startup FF-45:** 1-2 hours, independent of live data; complete before FF-47.
- **Responsive/usability FF-46:** 1-2 hours; inspect stable views now and finish affected reruns after frontend changes. It joins at FF-47, not after FF-44.

Do not inflate the minimum path with optional redesigns, a new testing platform, unrelated warning cleanup or a new schema-migration framework when no incompatible schema change is required. Conversely, off-path means parallel scheduling, not permission to skip required behavior or evidence. FF-19 must preserve existing saved data if any mapping change affects units.

### Execution sequence

1. **Start FF-18 first.** Source data is the limiting factor, not SQLite or missing CRUD. Timebox feasibility before broad parser changes. If 15 fully quantified records cannot fit the allowed catalog/exact mappings, surface the evidence and obtain a source/spec decision. The requirement stays open; a bigger synthetic corpus is not a resolution.
2. **Source critical path: FF-18 -> FF-19 -> FF-20 -> FF-21.** Keep one mapping owner to avoid contradictory identities/units. A reviewer may prepare fixtures for selected candidates concurrently, but corpus acceptance waits for the real normalizer.
3. **In parallel, finish FF-38 to FF-43.** Resolve yield semantics early. FF-38/FF-40 share detail files and FF-38/FF-43 share history labels: sequence those edits or use one frontend owner. CookDialog and pantry/shopping form corrections can be separate component workstreams.
4. **Start FF-45 and prepare FF-44/FF-46 now.** Offline startup verification needs no real corpus. Inspect stable mobile/keyboard paths early, then rerun affected interactions after UI fixes.
5. **Finish FF-44 while the independent FF-45/FF-46 acceptance branch closes, then FF-47 -> FF-48.** FF-46 does not need to wait for the real-source browser run: its final UI rerun can finish as soon as the relevant frontend changes land. Final docs wait for all three acceptance results. Do not repeat completed milestones or clean unrelated warnings before the blocker is addressed.

Serving-yield semantics (FF-38) are a second unresolved source/product question. A whole batch is not evidence of one human portion. Correct labels can prevent misleading UI, but literal spec compliance still needs trustworthy yield evidence or an explicit accepted interpretation.

### Parallel ownership proposal

| Lane | Work | Ready now | Coordination / join |
| --- | --- | --- | --- |
| A - Source/normalization | FF-18 to FF-21 | FF-18 | Own catalog/importer; independently review amounts before corpus closure |
| B - Frontend completion | FF-38 to FF-43 | Yes, subject to yield evidence | Coordinate detail/history edits; separate component work may overlap |
| C - Acceptance/docs | FF-45; prepare FF-44/FF-46/FF-47 | Independent checks/preparation | Final checks wait for corpus and required UI changes |
| Integration owner | FF-48 | No | Join after required work/evidence; preserve contract/design |

These are suggested contributor workstreams, not agents spawned or assignments made during this review. Do not add an issue per lane or per recipe: the 48 issue bodies are the backlog.

## Total remaining MVP effort (distinct from critical-path time)

Engineering effort is not guaranteed elapsed time. Completed issues have **zero remaining implementation effort**. Source changes, connectivity and a necessary source/spec decision can add unbounded waiting time.

| Group | Issues | Base effort |
| --- | --- | --- |
| Real supported corpus | FF-18 to FF-21 | 9-20 hours |
| Focused frontend/semantic completion | FF-38 to FF-43 | 6-14 hours |
| Browser/startup/mobile/docs/sign-off | FF-44 to FF-48 | 5-9 hours |
| Total before contingency | 15 remaining issues | **20-43 hours** |
| With integration/review contingency | Same scope | **25-55 hours**, approximately 3-7 full working days for one contributor |

With suitable parallel contributors and feasible mappings, the expected 12-25-hour serial branch (15-32 hours with contingency) may govern elapsed work; availability, review handoffs and independent branches can extend it. This is not a promise that total effort shrinks when work is parallelized. Re-estimate after FF-18. There is no honest fixed finish date if 15 recipes or trustworthy yields cannot be obtained without relaxing requirements. The original 12-hour whole-project aspiration is not a remaining-work commitment.

## Review and future GitHub handling

Review issue boundaries, especially FF-18/FF-19 feasibility and FF-38 interpretation. Approval of this document alone does not waive acceptance criteria or authorize fabricated conversions. No fixes are performed by this planning change.

If later explicitly authorized to create GitHub issues: use these six milestones, translate FF dependencies into real issue links, label each issue with its exact classification plus priority/area/readiness, attach completed commit/test evidence, and close only the 33 MVP-completed entries. Keep all 15 MVP-remaining entries open until their criteria are met. No Post-MVP issue is proposed; do not create optional tasks to fill a category. Do not rewrite history, push repository changes or publish as part of issue bookkeeping without authorization.
