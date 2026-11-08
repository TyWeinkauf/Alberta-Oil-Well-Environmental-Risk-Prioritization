# Reproducibility and verification

Run commands from the repository root unless an absolute script path is used. Setup does not download official well/environmental data. After Python dependencies and PostgreSQL/PostGIS are installed, the demo and tests need no external data or network connection.

## Repeatable commands

Activate the managed environment and start PostGIS as shown in the root README, or configure a normal local virtual environment and `.env`. Then:

```bash
python scripts/setup_db.py
python scripts/demo_seed.py
python scripts/demo_seed.py
pytest -q tests/unit
```

For all tests, create a separate empty `alberta_risk_test` database and set `TEST_DATABASE_URL` as documented in the README:

```bash
pytest -q --junitxml=outputs/test-results.xml
```

Missing `TEST_DATABASE_URL` explicitly skips integration tests. A test target whose name does not end in `_test`, or one with an existing `screening` schema, is refused. The schema created by an integration test is removed afterward; the application database is not a test target.

## Evidence from 8 November 2026

- Python **3.12.14**, PostgreSQL **17.5**, PostGIS **3.5** on Linux.
- All 67 pinned requirements installed into a new virtual environment from the managed cache; package compatibility check passed. The new virtual environment, with its own bundled pip, ran the repository tests and both CLI commands.
- Migration setup applied the initial migration to a fresh schema in integration tests. Repeating setup returned no pending migrations; changing applied migration contents was rejected. A deliberately failing migration rolled back its tables and ledger.
- The committed fixture produces **2 accepted wells + 2 accepted environmental features + 6 quarantine records = 10 input records**, with 0 production and 0 proximity rows. Duplicate IDs are rejected in both occurrences; invalid geometry, missing required fields and out-of-extent points have named reasons.
- The demo run ID is `daab2b74-8a43-5955-b5fc-c4cf8a025029` for the current fixture/config/contract version. Running it twice returned the same ID, counts and report content; the database held one run and one source snapshot.
- A trigger-induced load failure rolled back the entire new run, including wells inserted before the failure. An unknown CRS did not alter the previous seed. A corrupt raw cache was detected and left unchanged.
- Tests also cover source-configuration gating, malformed extents/thresholds, optional fields, CRS reprojection, invalid geometry/category handling, database uniqueness and geometry-type constraints.

The current test result is recorded in `DESIGN.md` and generated XML under `outputs/`. Generated evidence stays outside Git. Run the commands again to produce fresh evidence on another machine; this report does not claim Windows execution or a completed web app/spatial-analysis demo.

## Inspect outputs

```sql
SELECT run_id, status FROM screening.pipeline_runs;
SELECT source_well_id, licensee_name, ST_SRID(geom) FROM screening.wells;
SELECT reason_code, count(*) FROM screening.quarantine_records GROUP BY reason_code;
```

Generated paths:

- `data/raw/<fixture_sha256>/demo.json`: exact input bytes, reused only after checksum verification.
- `outputs/runs/<run_id>/manifest.json`: source/config identity, counts, study extent, validation and disclaimer.
- `outputs/runs/<run_id>/validation.json`: accepted/rejected accounting and row-level reasons.
- `outputs/test-results.xml`: current pytest outcome when requested.

Do not edit an applied SQL file, reset the application schema or delete the persistent database volume to refresh setup. Add a new numbered migration for schema changes. To change the fixture/config intentionally, retain previous run evidence and expect a different run UUID. The contract-version marker in the seed must change when validation semantics change.

The synthetic seed commits as `seeded`; it does not claim production attribution or spatial screening. All design acceptance items involving the complete app, proximity results, production data or real-source failure handling remain open for later phases.

## Phase 2 verification — 8 November 2026

Run `python scripts/setup_db.py` to apply migration 002, then `python scripts/analyze_demo.py`. Default water distances are 50 m and 150 m; analysis creates 10 well/category rows. The generated `analysis.json` reports matches changing from 2 at 500 m to 1 at 50 m, affecting DEMO-WELL-002. A repeat uses the same run and preserves row counts; unchanged reseeding preserves derived results.

The complete current suite passed **61 tests (44 unit, 17 PostGIS integration), with no skips or warnings**. It covers boundary distances, points inside polygons, actual line geometry versus centroids, stable equal-distance ties, selected-category recomputation, missing/incomplete coverage, run isolation, rollback of failed recalculation, and invalidation of results after a coverage downgrade. Both default-water and combined water/protected-area CLI selections were exercised, plus the 50 m threshold.

The main demo's protected-area coverage is incomplete because its invalid polygon was quarantined. Adding that category makes the exact overall band unknown. A known water positive is still reported, while an unsupported negative is not fabricated. The clean boundary fixture separately tests complete-category minimum distances. See [methodology](spatial_methodology.md).

The [provided real-data reference](dataset_reference.md) has been recorded in the catalogue. It does not supply endpoint URLs/layer IDs, and no live-data acquisition or web UI is claimed by these checks.

## Phase 3 verification — 8 November 2026

The full Python suite passed **67 tests (48 unit, 19 integration), no skips or warnings**. After final UI export/empty-result changes, the two dashboard integration checks were rerun successfully. Tests initialize an empty test database through the actual Streamlit Use demo dataset action, then check counts, detail selection, threshold/company filters, selection outside the current filters, empty results and no extra ingestion on widget reruns.

A real headless Chromium run of `node tests/browser/ui_smoke.cjs` passed with all remote HTTP requests blocked. It verified explicit workflow completion, clicks on both well markers, persistent selection, threshold/match/company filters, matching counts and CSV/GeoJSON/manifest downloads, data quality/history views, and a standalone downloaded HTML map displaying exactly the one filtered marker. The browser test caught and verified fixes for the component's plain-text popup bridge and duplicate HTML markers caused by reusing a figure mutated by streamlit-folium. Downloads do not rerun the app.

The offline map uses licensed vendored Leaflet/jQuery assets with recorded SHA-256 checksums. A direct fresh request to an OpenStreetMap tile was denied by the managed proxy (CONNECT 403); the required `tile.openstreetmap.org` allowance and actual app startup instructions were saved to the environment draft. Saving did not apply or publish them. Online tiles are not claimed as verified.

Start the app with `streamlit run app.py` after activating the environment and starting PostgreSQL/PostGIS. The UI checks are synthetic development evidence; real data from the supplied sources remains the intended final project input. See [UI workflow](ui_workflow.md).

## Phase 4 partial verification — 8 November 2026

The full current suite passed **80 tests (57 unit, 23 integration), no skips/warnings**; affected acquisition tests are rerun after final cache/provenance refinements. The offline Chromium smoke also passed after readiness-gated live controls and persisted attempt history were added. `scripts/setup_db.py` applied migration 003 successfully to the prepared database. `scripts/run_live.py` was exercised and correctly refused the unverified official catalogue before creating a partial run.

New tests acquire generated Shapefile, GPKG and OpenFileGDB ZIPs through local HTTP; inspect CRS and bounded subsets; exercise retries, conditional responses, byte/total budgets and corrupt-cache rejection; enforce ArcGIS count/ID-page completeness; and validate the live 500 m geometry margin. Simulated four-source integration verifies immutable bundles, original retrieval timestamps, one run on unchanged repeats, per-category coverage, failed-page retention and database rollback after a forced spatial-load error.

These are synthetic protocol tests, **not official source data**. Fresh requests to the four official discovery hosts were rejected by the proxy with CONNECT 403. Their domains are saved in the environment draft but not applied; actual publisher terms/endpoints/layers/fields/CRS and the Drayton Valley regional run remain unverified. Phase 4 remains in progress. See [source verification](source_verification.md).

The separately published OpenStreetMap tile rule was retested with a fresh request and returned HTTP 200. That does not establish access to analytical data hosts.

## Phase 5 partial verification — 8 November 2026

The complete Python suite passed **103 tests (72 unit, 31 integration), no skips/warnings**. The eight production integration checks were rerun after final month-window/API refinements. Both the existing offline map browser smoke and the new production browser smoke passed against a freshly restarted application after the schema upgrade.

`python scripts/demo_production.py` was executed and repeated successfully: 9 synthetic input records, 6 accepted, 2 quarantined and 1 outside the window. Three observations have exact unique synthetic well links; facility, unmatched and unknown-level records remain audit-only. The active batch and monthly rows are not duplicated on a repeat. Forced insertion failure preserves the prior active batch; ambiguous exact identifiers cannot populate a chart. Synthetic import on a real-source run and cross-run well reads are rejected. A simulated remote transport failure persists an error class/stage without the underlying connection message.

The real Chromium production check clicked the explicit synthetic import, rendered DEMO-WELL-001's monthly chart, switched from oil production to its separate adjustment series, switched to DEMO-WELL-002's unavailable state, and downloaded an audit retaining the 900-unit facility observation outside either well chart. Exact table decimals and source provenance remain separate from floating-point plot coordinates. The CSV inspection helper was also executed against the project-authored fixture and reported its headers/sample.

Actual Petrinex discovery was denied by the proxy (CONNECT 403). Its host was added to the existing pending draft domain list; actual public access, grain, licence, fields, units and well-identifier semantics remain unverified. **No real production has been ingested and Phase 5 is not complete.** Save/apply pending network settings before official verification and a real refresh can proceed. See [production](production.md).
