# Candidate release verification and recovery

**Historical candidate receipt:** The code digest and two-browser evidence below precede the user's removal of Petrinex. Current defaults now contain AER/environment sources only. The revised scope has its own 118-test and default map-browser evidence; retained production tests opt in through custom catalogues. See [scope/download instructions](download_inputs.md) and [current scope evidence](evidence/current_scope_2026-11-08.json).

The Phase 6 candidate has **118 passing Python tests** and both offline Chromium checks passing. [Retained evidence](evidence/release_verification_2026-11-08.json) records the tested code-tree digest, requirements digest, counts, commands and bounded benchmark. Real official input/schema validation remains open in Phases 4–5.

## Isolated checkout and dependency verification

Verification used a new local Git clone of base commit `98d290479be6a765595b3d5b8e094ee1188c0715`, overlaid with the uncommitted candidate changes. It began without `.env`, raw/cache inputs or generated outputs. A new Python 3.12.14 virtual environment, without system-site packages, installed all **67 pinned packages** offline from the local uv cache. `uv pip check` passed. The complete suite passed **118 tests, zero failures/errors/skips** in that environment.

A newly created disposable PostgreSQL database then ran `setup_db.py` twice, `demo_seed.py` twice, `analyze_demo.py`, and `demo_production.py` twice. Commands were invoked by absolute path from outside the checkout to verify script bootstrapping. Repeats retained:

| Entity | Stored count |
|---|---:|
| Spatial run | 1 |
| Wells / environmental features | 2 / 2 |
| Spatial quarantines / proximity rows | 6 / 10 |
| Production batch / observations | 1 / 6 |

The 500-to-50 m threshold sensitivity changed matched wells from 2 to 1, affecting `DEMO-WELL-002`. A Streamlit server from this new environment passed `ui_smoke.cjs` and `production_smoke.cjs`, with external browser requests blocked. Checks cover marker selection, filters, export parity, standalone HTML, the production chart and separate adjustment series, unavailable other-well production and audit-only facility quantities. The temporary app was stopped and its newly created database removed.

This is Linux candidate-source evidence, including a fresh dependency environment. It does not provision PostgreSQL or the operating system, verify Windows, acquire official data, or verify the eventual GitHub release commit. Repeat the checkout smoke against that exact commit after it is committed/pushed. The repository's Windows instructions remain unexecuted.

## Concurrency and recovery behavior

Public mutation workflows acquire the same database-wide PostgreSQL advisory lock before acquiring inputs or changing data. Competing imports, migrations or analyses fail immediately with `WorkflowBusy`; the app tells the user to wait and retry. Read-only maps, filters and exports can continue. Nested operations on the same engine reuse the guard. At least two available database pool connections are needed; one holds the session lock while others perform transactions.

Tests hold a lock from another thread/session and verify rejected writes plus an informative busy UI. A fault-injection check also verifies cleanup after a guard-setup commit error using a separate connection pool. Another test kills a child process holding a lock and an unfinished attempt: the next mutation acquires the released lock, marks the attempt `failed` with `InterruptedWorkflow`, and reuses the existing active production batch without losing the ten proximity rows. A forced production-manifest write error rolls back the new batch; retry succeeds after the export fault is removed.

For a stopped or failed run:

1. Inspect Run history, Data quality and the selected dataset's provenance. A busy message alone does not mean failure; wait for a live owner to finish. Do not reclaim locks using an age threshold.
2. If the process stopped, restart the application and repeat the explicit action. PostgreSQL releases a dead session's lock. The next mutation marks abandoned running attempts interrupted, retaining their original stage and committed results.
3. Use the same unchanged inputs/window to verify stored counts and regenerate missing reports. Check the active batch before repeating a production refresh with another window; window changes intentionally create another batch.
4. If input/cache corruption is reported, restore trustworthy original bytes or use a separately configured clean cache location. Do not edit applied migrations or overwrite immutable archives to suppress the error. Keep prior successful results until replacement inputs pass validation.

PostGIS determines which results committed. Files and database commits are not a distributed transaction, so an orphan report/cache file is not evidence of a successful dataset. A process stopped after a commit but before completing its audit may leave usable committed data; the interrupted message therefore asks the user to inspect it rather than claiming no data committed. Stop old unguarded app versions before deploying this coordination change. Test-database cleanup is confined to the schema/database created for the check.

## Bounded performance baseline

```bash
python scripts/benchmark_pipeline.py --wells 1000
```

Set `TEST_DATABASE_URL` to a **separate initially empty database ending in `_test`**, using the same PostgreSQL/PostGIS prerequisites as integration tests. The command rejects an existing `screening` schema, holds the workflow lock throughout, and removes only the initially absent schema it created. It saves a summary under ignored `outputs/verification/benchmark.json`. Never point it at the application database.

The measured case uses synthetic well CSV and three GeoJSON sources: **1,000 wells, 30 features, 5,000 proximity rows**. First load/acquire/analyze/report took **0.2953 s**, repeat took **0.1851 s**, and dashboard/filter/CSV export took **0.0534 s**. The repeat used one run with unchanged counts; the export contained 1,000 rows. These are single-machine observations of two runs, not a throughput guarantee or province-wide scaling proof. Real geometry sizes, download latency and storage volumes require further measurements.

## Handoff still required

The separate [AIDA 1145 evidence index](../aida-final-project-tyler-weinkauf/courses/AIDA-1145/EVIDENCE.md) and [AIDA 2362 evidence index](../aida-final-project-tyler-weinkauf/courses/AIDA-2362/EVIDENCE.md) identify the current methods and checks. They are candidate indexes, not submitted course packages. Finish actual-data provenance/permissions, real-source outputs and interpretation; add final screenshots, presentation/review evidence, and package each course according to the current instructor/D2L requirements. Verify the final committed checkout and the intended user platform. Phase 6 remains in progress until those deliverables are supported by evidence.
