# Original FreshFirst catalog, revision v2

The 80 `ff-original-001` through `ff-original-080` identities are retained from
v1. The v2 revision edits their content individually: quantities, defining
ingredients, methods, timing and intended yield. Earlier prefixed duplicates
are not counted as independent recipes. All 80 current recipes have different
core ingredient identity sets, even when quantities and basic cooking
water/oils/butter/salt/pepper are ignored. No records were added or removed.

These are **AI-assisted original recipes, not kitchen-tested**. They are not
TheMealDB responses and carry no external-source or human-testing claim. The
existing `original-authored://freshfirst/catalog/v1/<id>` provenance addresses
remain stable identifiers, not working image/download links. The independently
captured real TheMealDB baseline and its source evidence remain unchanged.

`base_servings=1` retains the application's whole-batch contract. Each recipe
states its authored intended `authored_portions` per complete batch in both
metadata and visible instructions. Selecting two batches doubles every exact
ingredient amount; it does not reinterpret two as human servings. Preparation,
cooking and additional resting/chilling minutes are recorded separately.
Quantified cooking water is included in inventory demand; no implicit stock,
seasoning, oil, density, package size or serving conversion is assumed.

The manifest hash is SHA-256 over UTF-8 JSON of `records`, with sorted keys,
compact separators and `ensure_ascii=False`. Each stored record also retains
its raw-source hash and ingredient-line audit through the existing importer.
Newer persisted records and their audits are preserved by missing-only startup.

`catalog_quality.validate_catalog` validates the entire package before returning
any record. Machine-readable `CatalogValidationError.code` and `.external_id`
identify rejection reasons (also available with `.as_dict()`). A bad package is
rejected as a whole; it never contributes a partial count or partial writes.
Checks cover the version/hash, identity/provenance, quantities/units, complete
slots, distinct core identities, defining title ingredients, detailed methods,
timing/yield and category consistency. These checks catch known defects; they
do not replace independent culinary review or assert real-world kitchen tests.
The current accepted count is 80, with zero excluded records. Negative tests
re-sign deliberately corrupted fixtures to exercise the actual quality gates.

Verification uses `tests/test_issue68_catalog.py`. The shared
`tests/catalog_transaction_probe.py` exercises the whole 80-recipe import with
an actual late database-constraint failure, full-table rollback comparison,
repeat import, saved user state, newer source preservation and a separate
process restart. The existing Compose CI runner executes that same probe in a
fresh isolated PostgreSQL database. Authenticated Playwright tests cover the
expanded catalog's combined filters/empty/loading/error states and a scaled
recipe -> basket -> edited purchase -> transfer retry -> cooking/history ->
app restart journey. No production database is used by these checks.
