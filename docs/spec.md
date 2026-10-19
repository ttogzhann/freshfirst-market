# FreshFirst v1.0 — Product Specification

## 1. Purpose and constraints
FreshFirst is a local, single-user full-stack application that helps people use food before it expires, discover suitable recipes, make ingredient substitutions, calculate consolidated groceries for several recipes, and update pantry inventory after cooking or shopping.

**Development time target:** 12 hours with a coding assistant; a target, not a guarantee. **Non-goals:** authentication, deployment, weekly calendar, AI-generated recipes, receipt scanning, nutrition/calorie tracking, price tracking, push notifications, multiple households, complex charts.

**Stack:** React + TypeScript (Vite), FastAPI, SQLAlchemy, SQLite, OpenAPI, tests. Frontend communicates with backend through one service interface. UI is an English-language, responsive desktop-first app with sidebar navigation: Dashboard, Pantry, Recipes, Basket, Shopping List. Backend is the source of truth for calculations.

## 2. Development workflow (strict order)
1. Write this specification in `docs/spec.md`.
2. Build an interactive React frontend using a centralized `Recipe/Pantry/Shopping` service interface and a mock implementation; add frontend tests.
3. Derive root `openapi.yaml` from frontend service calls; specify operations, input/output schemas, errors, and no authentication.
4. Build a FastAPI backend conforming to OpenAPI with a seeded in-memory store, modular routers/services and tests.
5. Switch frontend from mock service to real HTTP client, configure CORS, and test user flows.
6. Replace the in-memory store with SQLite + SQLAlchemy, database URL configurable by environment variable; seed catalog and recipes; test persistence across restart.
7. Document local startup and verification in README; make regular Git commits. No deployment, Docker, CI/CD, or Postgres for v1.0.

Recommended repository layout: `frontend/`, `backend/`, `docs/spec.md`, `openapi.yaml`, `AGENTS.md`, `README.md`.

## 3. Core user journeys
### 3.1 Pantry
- Browse a predefined product catalog (approximately 25–40 common ingredient identities) and add an item by choosing ingredient, quantity, compatible unit, and expiration date.
- Edit/remove a pantry item; browse product cards, search, filter by ingredient category and expiry status.
- For v1.0, one pantry entry per ingredient; adding a second entry combines only if unit can be normalized and uses the single stored expiry date only when unchanged; otherwise warn and require editing the current entry. This is an intentional simplifying restriction: separate expiry batches are out of scope.
- Expired items remain visible and editable but count as **zero available** for matching, substitution, groceries and cooking. Products near expiry are highlighted using a configurable fixed threshold of 3 days (not a food-safety guarantee).

### 3.2 Recipe import and discovery
- Import 15–20 **supported** recipes automatically from TheMealDB via the backend, store normalized recipe data and the source identifier in SQLite; do not hand-enter recipe records. Include instructions, category and image URLs.
- Import is an explicit backend operation / idempotent startup seed, not repeated on every page render. Re-import should update/upsert by source ID instead of duplicating.
- Accept only recipes whose ingredient identities and required quantities can be mapped confidently to the supported catalog and canonical units. Unsupported recipes are skipped with an import report explaining why, until the target catalog of 15–20 is reached. If the external API is unavailable, previously imported recipes remain usable; initial import requires connectivity.
- Because external recipes may use ambiguous measures (e.g., pinch, handful, cup without ingredient-specific density), never guess conversion coefficients. Handle g/kg, ml/l and unit/count (`pcs`), and allow explicitly mapped kitchen measures only where exact conversion is defined in a normalization table. Unsupported quantities must not feed exact grocery or inventory calculations.
- Search by title and filter by category. Rank recipes by availability of ingredients/required quantities and by urgency of non-expired pantry items expiring within three days. Show a match score, missing ingredients and expiry-relevant notes; never claim an unquantified recipe can be cooked fully.
- Match percentage is `number of required ingredient lines adequately covered / total required ingredient lines * 100`, rounded to whole percent; substitutions do not silently increase the percentage before approval. Expiry is a ranking tie-breaker or bonus, not a guarantee of food safety.

### 3.3 Recipe details and substitutions
- Show title, image, category, instructions, base serving count, ingredient list, availability/missing state, and adjustable serving count (integer 1–8).
- Scale canonical quantities by `requested_servings / base_servings` consistently across substitutions, grocery list and cooking.
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
- Cooking history is a simple list; no analytic waste estimates.

### 3.7 Dashboard
- Show total pantry items, soon-expiring item count, expired item count, `Cook These First` recipe recommendations, and recent cooking history.
- No complex charts or speculative food-waste-saved metrics.

## 4. Validation, errors and UX
- Require positive quantities, compatible units, valid calendar dates, non-empty required fields, serving count 1–8. Expired date is allowed for recorded pantry items but never treated as cookable stock.
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
4. Imported recipes are 15–20 valid normalized recipes, without duplicate external IDs on repeated import.
5. Unsupported free-text ingredient quantities are rejected/skipped with an import report, not guessed.
6. Changing servings scales all ingredient demands; confirmation-only substitutes update the demands.
7. Persistent basket survives page refresh and backend restart.
8. Shopping calculation aggregates shared ingredients and deducts pantry stock once, including g/kg and ml/l.
9. Manual shopping edits do not vanish silently on regeneration.
10. Confirmed purchased item is added to Pantry exactly once.
11. Cooking with insufficient stock leaves inventory and history unchanged; valid cooking deducts stock and creates history in one transaction.
12. API errors and validation failures display understandable messages; no UI false success.
13. Tests cover each computation and critical backend endpoint; end-to-end manual walkthrough covers Pantry → Recipes → Basket → Shopping → Purchase → Cook → Restart.

## 8. Scope and time protection
- Implement the required features above at simple UX depth, rather than adding features.
- Strictly avoid authentication, deployment, multi-user sync, nutrition, unrestricted API importing, weekly calendar, advanced conversions, multiple expiry lots, elaborate charts, and external integrations beyond recipe import.
- Split GitHub work into small independently testable Issues, closed only when implemented and verified; no arbitrary issue-count requirement arises from the supplied article.
- Aim for 12 hours, but API normalization + inventory consistency are project risks: do not assert this timeline is guaranteed.
