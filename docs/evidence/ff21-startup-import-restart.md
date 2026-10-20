# FF-21 startup, import and restart evidence

Engineering observation on 2026-10-20; acceptance revision [FF21-PM-r1](https://github.com/ttogzhann/freshfirst-market/issues/21#issuecomment-6282325872). This is an engineering handoff, awaiting independent QA on the committed candidate. No application correction was necessary.

## Reproduction and isolation

From `backend/`, use the locked environment:

```powershell
$env:UV_CACHE_DIR='../.uv-cache'
../.tools/uv/bin/uv.exe run --locked pytest -q tests/test_startup_http.py tests/test_offline_baseline.py tests/test_importer.py tests/test_persistence.py
../.tools/uv/bin/uv.exe run --locked python tests/startup_smoke.py --directory ../.tools/ff21-offline-new
# Opt-in: ONE actual import attempt; keep a different fresh directory.
../.tools/uv/bin/uv.exe run --locked python tests/startup_smoke.py --directory ../.tools/ff21-live-new --live
```

The smoke refuses an existing `smoke.db`; it constructs an absolute SQLite URL inside the supplied directory. Each launch runs normal `app.main:app` through uvicorn in a new Python process, using default initialization. Readiness is bounded to 15 seconds, HTTP import to 90 seconds; the default source retains its production 5-second connect/15-second request limits and TLS verification. There is no source substitution in live mode. Offline mode blocks non-loopback socket connections in the backend process. `result.json` contains the complete HTTP import report, serialized before/after recipe/basket/pantry state and restart comparison. Each process's startup/access logs are retained alongside it. All children stop in `finally` even on failure. A caller timeout is a failed observation, never application error-envelope evidence.

Pytest uses disposable directories automatically. For manual runs, after both servers have stopped, delete only the specifically created smoke directory with `Remove-Item -LiteralPath <absolute-created-directory> -Recurse`; never use an existing user database. The paths above are ignored development artifacts, not required production files. The recorded live observation below used an equivalent initial runner and `.tools/ff21/live.db`; no second live import was made while packaging the reproducible command.

## Observations and criterion mapping

| Criterion | Evidence                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| --------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| AC-01     | Real HTTP fresh startup returned exactly `rec_53137` / external ID `53137` and `rec_52776` / `52776`. Both have nonempty original title/category/instructions/image and `base_servings=1`, meaning whole-source batches. The test asserts all ten quantities listed below.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| AC-02     | Reproducible blocked-network smoke at 03:03:58 UTC (08:03:58 Asia/Qyzylorda) became ready in 1.328 seconds; reopening became ready in 1.266 seconds. Logs show normal uvicorn application startup and HTTP requests, with no obsolete fifteen-recipe warning. Default startup never traverses the live source.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| AC-03     | The HTTP test saves the two recipe selections at scales 2 and 3, fails an explicit import, terminates the backend, starts a distinct normal backend process on the same file and compares complete serialized recipe/basket/pantry state. SQL confirms 2 recipes, 10 ingredient rows, one canonical milk identity and no foreign-key violations. Existing `test_partial_baseline_retains_newer_live_and_every_saved_entity` additionally proves a newer baseline title/2L quantity and a third valid deterministic recipe, basket, pantry, shopping and cooking history survive repeated missing-only seed and separate-interpreter reopening. Existing offline startup test deletes all stock and proves repeat seed/restart does not refill it. These synthetic additional-record checks are separate from the genuine baseline. |
| AC-04     | ONE real `POST /api/recipes/import`, 03:03:12 UTC (08:03:12 local), completed HTTP 200 in 4.297 seconds. Actual report: imported **0**, updated **2**, skipped **788**, total recipes **2**. Before/after IDs were `[rec_52776, rec_53137]`; full recipe/basket/pantry state was equal, including saved scales 2 and 3. Separate-process offline reopening took 1.281 seconds and was equal again. This is a successful production adapter traversal, with strict unsupported lines skipped; it is not 790 supported recipes or a fifteen-recipe requirement.                                                                                                                                                                                                                                                                      |
| AC-05     | New actual-adapter test feeds unaltered packaged captures through `httpx.MockTransport` into `TheMealDBSource`, imports twice via contract-validated HTTP and checks report `(0 imported, 2 updated, 2 total)` and unchanged serialized state/basket scale 4. Real-HTTP socket-blocked import returns the exact 502 envelope below and preserves serialized state. Existing adapter tests cover timeout, HTTP, malformed JSON/shape/list after a valid candidate, proving traversal cannot partially write.                                                                                                                                                                                                                                                                                                                        |
| AC-06     | Focused regression cases and opt-in smoke are committed with this evidence. Required check results below; independent QA remains the next gate.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |

Exact canonical source quantities:

- 53137: milk 1000 ml; sugar 300 g; baking_powder 1.25 ml; vanilla 5 ml.
- 52776: plain_chocolate 250 g; butter 175 g; milk 30 ml; egg 5 pcs; sugar 175 g; flour 125 g.

Both recipes reference the same canonical `milk` and `sugar` identities. Source provenance and unaltered raw payloads are in [the packaged manifest](../../backend/app/data/mealdb-source/provenance.json), [53137](../../backend/app/data/mealdb-source/53137.json) and [52776](../../backend/app/data/mealdb-source/52776.json). Original URLs are [lookup 53137](https://www.themealdb.com/api/json/v1/1/lookup.php?i=53137) and [lookup 52776](https://www.themealdb.com/api/json/v1/1/lookup.php?i=52776); captures were acquired at 02:09:37 UTC on 2026-10-20. Live import uses the existing alphabet search endpoint, with no further source discovery or normalizer changes.

The deliberately blocked offline explicit import completed in 0.094 seconds with HTTP 502 and this unchanged envelope:

```json
{
  "status": 502,
  "code": "SOURCE_UNAVAILABLE",
  "message": "TheMealDB is unavailable or returned invalid data. Previously imported recipes are unchanged."
}
```

## Checks and limits

- `uv run --locked pytest -q tests/test_startup_http.py`: 2 passed, one existing Starlette/httpx deprecation warning.
- `uv run --locked pytest -q`: 123 passed in 13.11 seconds, same one warning; includes startup/importer/persistence/contract suites.
- `uv run --locked ruff check app tests`: passed.
- `uv run --locked ruff format --check app tests`: passed, 29 files after adding the smoke helper.
- Frontend `npm run validate:api`: passed, OpenAPI 3.0.3, all 23 operations match, no authentication.
- Offline opt-in smoke: HTTP 502, bounded readiness, restart equality as above.

Node was inaccessible in the sandbox PATH on the first contract attempt; the same required command passed using the installed Node environment outside that restriction. No dependency, API/schema, production source, frontend or inventory behavior changed. Frontend browser acceptance belongs to #44 and was not run here. Live-source contents and timing can change; deterministic captures remain the stable regression oracle. Engineering effort approximately 9 minutes; aggregate balance is maintained by the orchestrator without resetting earlier expenditure.
