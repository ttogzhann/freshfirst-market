# FreshFirst MVP v1.0 — Product Specification

## 0. Operative MVP boundary - 2026-10-20 revision

This is the requested 12-hour completion boundary for the existing implementation, not a claim that it is implemented or tested. The change log in section 9 records the original decisions and their replacements. Existing API operations, response schemas, working UI features and persisted data are preserved. Recipe-corpus breadth, source bootstrap, human-yield interpretation and history-browser depth change explicitly; inventory correctness is not narrowed.

The smallest complete journey is: manage pantry -> choose two real supported recipes -> set batch counts and explicitly confirm eligible substitutions -> persist a basket -> generate shared shopping demand -> record actual purchased quantity/expiry -> transfer once -> preview and confirm cooking atomically -> inspect recent history -> reload/restart and recover the same saved state. Existing search, category/status filters, matching/ranking, manual shopping edits, image/instruction display, configurable expiry behavior and responsive shell remain available.

The implementation currently provides the architecture and core operations; the second real recipe, honest batch labels, saved-detail choices, failed-cook recovery and final integrated verification still need closure. A documentation revision alone does not complete them. See `docs/issues-plan.md` for issue-level acceptance, budgets and worktree ownership.

## 1. Purpose and constraints
FreshFirst is a local, single-user full-stack application that helps people use food before it expires, discover suitable recipes, make ingredient substitutions, calculate consolidated groceries for several recipes, and update pantry inventory after cooking or shopping.

**Remaining delivery budget:** a strict cap of 12 aggregate engineering hours for implementation, worktree setup/coordination, tests, integration and final documentation. Plan nine hours of scoped work and reserve three for overruns; parallel agents share the cap, rather than each receiving 12 hours. Existing implementation is retained. Budget allocation is not a guarantee of completion or evidence of hours already spent; debit actual planning/setup time before starting implementation. **Non-goals:** authentication, deployment, weekly calendar, AI-generated recipes, receipt scanning, nutrition/calorie tracking, price tracking, push notifications, multiple households, complex charts.

**Stack:** React + TypeScript (Vite), FastAPI, SQLAlchemy, SQLite, OpenAPI, tests. Frontend communicates with backend through one service interface. UI is an English-language, responsive desktop-first app with sidebar navigation: Dashboard, Pantry, Recipes, Basket, Shopping List. Backend is the source of truth for calculations.

## 2. Development workflow (historical delivery order)
1. Write this specification in `docs/spec.md`.
2. Build an interactive React frontend using a centralized `Recipe/Pantry/Shopping` service interface and a mock implementation; add frontend tests.
3. Derive root `openapi.yaml` from frontend service calls; specify operations, input/output schemas, errors, and no authentication.
4. Build a FastAPI backend conforming to OpenAPI with a seeded in-memory store, modular routers/services and tests.
5. Switch frontend from mock service to real HTTP client, configure CORS, and test user flows.
6. Replace the in-memory store with SQLite + SQLAlchemy, database URL configurable by environment variable; seed catalog and recipes; test persistence across restart.
7. Document local startup and verification in README; make regular Git commits. No deployment, Docker, CI/CD, or Postgres for v1.0.

Steps 1-6 describe the delivered foundation and must not be rebuilt for the deadline. Remaining work consists of focused fixes, a verified source baseline and final acceptance; preserve all 23 existing operations.

Recommended repository layout: `frontend/`, `backend/`, `docs/spec.md`, `openapi.yaml`, `AGENTS.md`, `README.md`.

## 3. Core user journeys
### 3.1 Pantry
- Browse a predefined product catalog (approximately 25–40 common ingredient identities) and add an item by choosing ingredient, quantity, compatible unit, and expiration date.
- Edit/remove a pantry item; browse product cards, search, filter by ingredient category and expiry status.
- For v1.0, one pantry entry per ingredient; adding a second entry combines only if unit can be normalized and uses the single stored expiry date only when unchanged; otherwise warn and require editing the current entry. This is an intentional simplifying restriction: separate expiry batches are out of scope.
- Expired items remain visible and editable but count as **zero available** for matching, substitution, groceries and cooking. Products near expiry are highlighted using a configurable fixed threshold of 3 days (not a food-safety guarantee).

### 3.2 Recipe import and discovery
- MVP must automatically seed **at least two distinct, fully quantified real TheMealDB recipes**, including a shared ingredient to demonstrate consolidated shopping. Store source ID, instructions, category, image URL and every normalized ingredient line in SQLite. Two is a revised minimum, not a claim that a second recipe has already been found. Preserve any additional already imported valid recipes and the existing import capacity; never truncate the database to two. Expanding the supported corpus to 15-20 is Post-MVP v1.1+ (FF-20). Do not hand-enter recipes or alter raw measures.
- Use a tiny reviewed baseline of unaltered TheMealDB API responses, with source URL/ID and capture date, as backend seed input. Pass these raw responses through the same strict normalizer and external-ID upsert used by live import. They are source snapshots, not synthetic fixtures or precomputed hand-entered recipe records. Seed only missing baseline external IDs; do not overwrite newer live records from an old snapshot. Repeated startup adds no duplicates or user inventory. Initial acquisition of raw data needs connectivity during preparation; a packaged baseline allows a fresh installed MVP to start offline. Keep the existing explicit live import operation and error/report schemas; do not replace it with mock success. No recurring whole-alphabet network scan should gate opening an already seeded database.
- Accept only recipes whose identities and all required quantities map confidently to the supported catalog and units. Unsupported records stay skipped with reasons. A bounded 30-minute feasibility check must identify two valid baseline records or report the release blocked; one accepted historical record is insufficient. Additional exact, reviewed aliases may be added only if meaning and stock dimension are unchanged. Do not expand the catalog broadly or reinterpret persisted canonical units under deadline pressure. Live-source failure leaves all stored recipes and user selections usable; a failed explicit live import still returns the existing failure response.
- Because external recipes may use ambiguous measures (e.g., pinch, handful, cup without ingredient-specific density), never guess conversion coefficients. Handle g/kg, ml/l and unit/count (`pcs`), and allow explicitly mapped kitchen measures only where exact conversion is defined in a normalization table. Unsupported quantities must not feed exact grocery or inventory calculations.
- Search by title and filter by category. Rank recipes by availability of ingredients/required quantities and by urgency of non-expired pantry items expiring within three days. Show a match score, missing ingredients and expiry-relevant notes; never claim an unquantified recipe can be cooked fully.
- Match percentage is `number of required ingredient lines adequately covered / total required ingredient lines * 100`, rounded to whole percent; substitutions do not silently increase the percentage before approval. Expiry is a ranking tie-breaker or bonus, not a guarantee of food safety.

### 3.3 Recipe details and substitutions
- Show title, image, category, instructions, ingredient availability and adjustable **whole-recipe batch count (integer 1-8)** for TheMealDB records without verified yield. One batch is exactly the complete source ingredient quantities. UI detail, basket, cook preview and history must say batches/recipe quantity, not infer how many people it serves. Existing API names `servings` and `base_servings` remain unchanged; imported `base_servings=1` means one source batch. No guessed serving conversions or new yield data model.
- Scale canonical quantities by `requested_servings / base_servings` consistently for substitutions, shopping and cooking. For unyielded TheMealDB records this is a batch multiplier, not a conversion to human portions. Reopening an existing basket selection must retain its saved scale and substitutions unless explicitly changed.
- If a required ingredient is missing/insufficient, suggest the best available substitute from a small predefined set of context-specific, reviewed rules (approximately 8–12 rules), showing required adjusted amount and explanation.
- Never apply substitution automatically: user explicitly confirms/rejects. Only suggestions with supported compatible quantities and enough non-expired substitute stock are eligible. Confirmed substitutions are stored for that recipe selection or cooking action.

### 3.4 Persistent recipe basket
- Add/remove recipes and set servings per selection; persist basket in database across refresh and backend restart.
- Avoid duplicates: adding same recipe updates its servings, rather than creating duplicate independent entries.
- Display all selected recipes and cumulative ingredient requirements. Quantities and substitutions are associated with a basket item.

### 3.5 Shopping list
- Generate a single shopping list from the basket: combine equivalent ingredient requirements in canonical units and subtract eligible pantry stock **once** across the whole basket. `to_buy = max(0, total_required - total_usable_stock)`.
- Apply confirmed substitutions before aggregation. Only compatible conversions are allowed; never combine mass and volume without verified ingredient-specific factors.
- Save generated shopping list; allow manual items, quantity overrides, removal and purchased checkboxes. Re-generating resets generated lines and preserves independently added manual lines unless user explicitly chooses to reset all; show a confirmation when it would overwrite user edits.
- For purchased entries, user confirms actual quantity and expiry date before adding to pantry. Completed purchase transfer must be idempotent to prevent double-counting. Purchased status alone does not change pantry.

### 3.6 Cooking and history
- User opens a recipe detail or basket item and clicks **I Cooked This**.
- Preview ingredient deductions, including confirmed substitutions and requested servings. Block confirmation if *any* usable ingredient is insufficient; do not allow partial or negative stock.
- Commit all ingredient deductions and cooking-history record atomically. On success show toast and recompute recommendations and shopping needs. Store recipe, date/time, servings, and ingredient quantities consumed.
- MVP history presentation is the existing simple recent-history list on Dashboard (up to five entries). Persist every cooking record and retain the existing full `listHistory` API; never delete older records because the UI shows only recent ones. A complete older-history browser list is a genuine Post-MVP UI enhancement (FF-43), without analytics.

### 3.7 Dashboard
- Show total pantry items, soon-expiring item count, expired item count, `Cook These First` recipe recommendations, and recent cooking history.
- No complex charts or speculative food-waste-saved metrics.

## 4. Validation, errors and UX
- Require positive quantities, compatible units, valid calendar dates, non-empty required fields and an integer selected scale 1-8. API serving-named fields retain their types; UI must explain batch semantics where yield is unavailable. Expired dates are allowed for recorded pantry items but never treated as cookable stock.
- Consistent toast notifications for create/update/delete/purchase/cook actions; inline validation, loading, empty states, and recoverable API error messages.
- Never show successful cook, import, or purchase completion before the backend confirms it. Handle API/network failures without corrupting local UI state.
- Sidebar is desktop-first with a simple responsive collapse on small screens.

## 5. Minimal data model
- `ingredients`: id, name, category, canonical_unit.
- `pantry_items`: id, ingredient_id (unique in v1), quantity_canonical, expiry_date.
- `recipes`: id, external_id (unique), title, category, instructions, image_url, base_servings.
- `recipe_ingredients`: id, recipe_id, ingredient_id, quantity_canonical, unit.
- `substitution_rules`: id, original_ingredient_id, substitute_ingredient_id, ratio, context, note.
- `basket_items`: id, recipe_id (unique), servings, confirmed_substitutions_json (or child table).
- `shopping_items`: id, ingredient_id nullable, label, quantity_canonical, unit, origin (`generated`/`manual`), purchased, transferred_to_pantry.
- `cooking_history`: id, recipe_id, servings, cooked_at, consumption_snapshot_json.

Use SQLite with SQLAlchemy, transactions for multi-row inventory operations, and a configurable DATABASE_URL. No users/auth tables.

## 6. Logical API operations (final names defined in OpenAPI phase)
- Catalog: list ingredients, list recipes (query/category/sort), recipe detail; import supported recipes with import report.
- Pantry: list/create/update/delete.
- Recipe: show match score, scaled ingredients, supported substitutes.
- Basket: get/add/update/remove and save substitution choice.
- Shopping: get/generate/add/edit/remove, mark purchased, confirm transfer into pantry.
- Cooking: preview cook, confirm cook, list cooking history.
- Dashboard: combined stats + recommendations.
- All mutating endpoints return validation errors and standard HTTP status codes, with explicit schemas in `openapi.yaml`.

## 7. Acceptance criteria / test matrix
1. A product added in Pantry survives page refresh and backend restart.
2. Expired stock is listed but excluded from availability, substitution, cooking and shopping calculations.
3. Recipes display meaningful match percentage; expiration urgency influences ranking.
4. A fresh installation seeds at least two distinct real fully quantified TheMealDB recipes, with a shared ingredient, complete metadata and no duplicate external IDs on restart or repeat import. The production baseline must not be synthetic. The original 15-20 target is preserved in the change log and FF-20 for v1.1+.
5. Unsupported free-text ingredient quantities are rejected/skipped with an import report, not guessed.
6. Changing batch count scales every ingredient by the same requested/base ratio; only confirmed substitutions alter demands. UI does not invent human portion yields, and saved basket choices survive reopening.
7. Persistent basket survives page refresh and backend restart.
8. Shopping calculation aggregates shared ingredients and deducts pantry stock once, including g/kg and ml/l.
9. Manual shopping edits do not vanish silently on regeneration.
10. Confirmed purchased item is added to Pantry exactly once.
11. Cooking with insufficient stock leaves inventory and history unchanged; valid cooking deducts stock and creates history in one transaction.
12. API errors and validation failures display understandable messages; no UI false success.
13. Keep all existing backend/frontend/contract checks passing and add focused regression tests for changed critical behavior. Record a complete manual Pantry -> Recipes -> Basket -> Shopping -> Purchase -> Cook -> Restart walkthrough with two real seeded recipes and shared-stock aggregation. Exercise a context-compatible substitution with real source data if available; otherwise use a separately labeled deterministic strict test source for that branch and do not present it as live-source coverage. Include stale-stock/failed-action recovery, offline startup, transfer retry and responsive navigation smoke checks.

## 8. Scope and time protection
- Implement the required features above at simple UX depth, rather than adding features.
- Strictly avoid authentication, deployment, multi-user sync, nutrition, unrestricted API importing, weekly calendar, advanced conversions, multiple expiry lots, elaborate charts, and external integrations beyond recipe import.
- Split GitHub work into small independently testable Issues, closed only when implemented and verified; no arbitrary issue-count requirement arises from the supplied article.
- Stop at the strict 12-hour aggregate delivery cap. Reserve time for integration and correctness checks; do not use it all on source discovery. If real baseline data or a core integrity/error bug remains unresolved, report MVP blocked with evidence rather than releasing a broken workflow or relabeling it Post-MVP.

## 9. Scope-decision change log - originals preserved

Revision requested on 2026-10-20 to define the smallest complete MVP within a strict remaining 12-hour delivery budget. This is a planning/specification change, not implementation evidence. Previous scope is preserved in Git at `13508ba` / `18d4955`; the preceding 48-issue classification is preserved at `18d4955`. Neither history nor application code is rewritten by this change.

| Decision | Original v1.0 boundary | Revised operative MVP v1.0 boundary | Disposition / reason |
| --- | --- | --- | --- |
| Time | 12 hours was an aspiration, not guaranteed | Strict aggregate remaining-work cap: nine planned hours plus three reserve; count parallel work and integration | Constrain effort and stop/report when correctness gates cannot close |
| Recipe breadth | Automatically import 15-20 supported real recipes; criterion 4 required that count | At least two distinct valid real records with a shared ingredient; keep all additional valid stored records and existing import capability | Corpus expansion to 15-20 is Post-MVP FF-20; this is an explicit product breadth reduction, not a completed original requirement |
| Initial source access | Fresh import required connectivity; previously imported data remained usable offline | Capture/provenance requires connectivity during preparation; install can seed missing IDs offline from unaltered reviewed raw TheMealDB responses through the same normalizer | Smallest deterministic baseline; explicit live import remains real and preserves its error semantics |
| Yield/scaling | Base serving count and selected servings 1-8 were shown without a source-yield policy; implementation used a whole source batch as one | Explicit whole-source-batch multiplier 1-8 when no verified human yield exists; API names/types and arithmetic unchanged | FF-38 remains MVP label/correctness work; no guesses or implied human portions. Verified human-yield enrichment can be considered later, but is not a new task here |
| History depth | Simple cooking history list plus recent Dashboard history; previous plan required full UI access via FF-43 | Keep all records and full API; recent five-record Dashboard list is sufficient MVP presentation | Full older-history UI is Post-MVP FF-43; no existing working history feature is removed |
| Integrity/errors | Atomic cook/history and purchase transfer, no negative stock, exactly-once transfer, expired-stock exclusion, persistent choices, recoverable errors | Unchanged and mandatory | FF-39/FF-40/FF-41/FF-42 and all existing integrity tests stay MVP; bugs cannot be traded for time |
| Existing breadth | Pantry filters, recipe discovery/ranking, substitutions, editable saved basket/shopping, responsive UI, SQLite and OpenAPI | Unchanged and preserved | No removal, redesign, authentication, deployment, PostgreSQL, Docker or new integrations |

**No silent fallback:** an ambiguous recipe is still unsupported; an insufficient or failed cook changes no partial inventory; an uncertain non-idempotent request is not automatically repeated. If the second valid real baseline record cannot be obtained without guessed conversions, MVP remains blocked even after the explicit breadth reduction. A one-recipe demo or synthetic production seed is not acceptance.
