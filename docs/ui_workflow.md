# Interactive workflow — Phase 3

Start local PostgreSQL/PostGIS, activate the Python environment, then run `streamlit run app.py` from the repository root. The root README has cloud and Windows commands. The application reads `DATABASE_URL`; it never displays credentials or raw database exceptions.

## Prepare and inspect a dataset

Choose **Use demo dataset** to explicitly run database preflight/migrations, synthetic ingestion/validation and proximity calculation. The visible status lists each stage and reports completion/failure. Existing valid analyzed datasets remain available in the study-area/dataset selector. Filter changes and marker clicks only read results; they do not rerun ingestion. Database transactions and locks protect the seed and spatial calculations.

The demo is development evidence. The completed app will use the real AER/provincial/federal stack in the supplied dataset reference. **Run full pipeline** uses the verified-source readiness gate: it remains disabled while current official catalogue entries are unverified, and becomes available only after all core sources and coverage notes are configured. The current catalogue contains no production source; no production buttons, chart or audit section appear by default. Optional legacy production UI is visible only when an enabled custom production source is explicitly configured. No real-source acquisition or well production is implied by the demo.

The map, result table and counts share one filtered record list. Available filters are licensee/company, status, environmental categories, threshold and known-threshold-matches-only. An empty company/status selection includes all values; an empty environmental-category selection produces unknown screening results. The incomplete demo protected-area layer remains unknown when selected. Company labels are explicitly licensees, with operator/producer values kept separate.

## Selection and details

Click a marker or use **Inspect a well**. The marker popup carries a stable database record reference through streamlit-folium's plain-text event bridge; coordinates are never used as a key. Details show well ID, source licensee, verified operator/UWI/LSD/status where present, coordinates, source snapshot information and per-category distance/coverage results.

Selection persists through normal rerenders and filter changes. If a selected well leaves the filtered result, the app says so and offers **Clear selection**, retaining its identity until the user clears it or changes dataset. Selecting another marker replaces the detail panel. Missing fields read “Not available from this source.” Well details show available AER-style attributes; missing fields remain unavailable. Monthly production is not required or displayed with the default catalogue.

## Offline and online map modes

Offline geometry is the default. Leaflet/jQuery/CSS are vendored with their licenses and SHA-256 manifest; no CDN is required. Valid environmental geometry can be overlaid. Optional **Show OpenStreetMap basemap (online)** uses the normal attributed tile layer and requires access to `tile.openstreetmap.org`. The published cloud policy now allows this domain, and a fresh tile request returned HTTP 200. The offline map remains available without network access. Analytical discovery hosts now respond; actual service/download access and schema verification remain incomplete. See [source discovery](source_discovery.md).

Colors follow the shared proximity bands. Gray can mean beyond the search radius or unknown; the exact band, coverage and cumulative flags are given in the table. Incomplete/unavailable source coverage is never displayed as a known negative. WGS84 is used for map/export coordinates; EPSG:3400 metres is used for distances.

## Exports and evidence

- **CSV / GeoJSON:** the same selected well IDs and values shown in the result table; GeoJSON is a WGS84 FeatureCollection with longitude, latitude ordering. Empty selections export zero features and CSV headers.
- **Map HTML:** a standalone version of the current filtered map, including embedded local library assets. Offline geometry/popups work without the Streamlit server. Online tiles still require network access if enabled at export time.
- **Selection manifest:** current filters, count, source checksums/retrieval/provenance, study area and coverage states.
- **Validation records:** quarantined rows with reason codes and raw references for the selected run.

Data quality shows source/coverage tables and rejected records. Run history shows analyzed datasets plus workflow outcomes/stages for the current browser session. Live pipeline attempts now persist their stage/outcome/error class in PostgreSQL and appear separately in Run history. The currently unverified official catalogue prevents actual live attempts; simulated protocol tests validate this audit path.

## Checks

`tests/unit/test_ui_model.py` verifies filters, stable-ID decoding, unknown states, CSV/GeoJSON parity, empty selections, popup escaping and vendored-asset hashes. `tests/integration/test_dashboard.py` exercises actual PostGIS dashboard reads and Streamlit AppTest actions, detail selection, threshold/company changes, persistence outside filters and no ingestion on widget reruns.

With the local app running, `node tests/browser/ui_smoke.cjs` runs the browser smoke test. The managed environment provides Playwright and `/usr/bin/chromium`; another development machine needs those tools, optionally selecting `CHROMIUM_PATH` and `APP_URL`. This check blocks remote HTTP requests to prove offline geometry behavior and exercises actual marker clicks, filters, matching downloads and standalone HTML. It does not claim online tile access.

## Legacy optional production detail and audit

Outside the current scope and only with an explicitly enabled custom production source, the Production expander accepts a month window, provides an explicit synthetic demo on demo datasets, and enables real refresh only for verified source configuration on a real-source run. Well charts use separate product/activity/unit series, with exact values and evidence in the table. Data quality exposes active-batch accounting, link outcomes, quarantines and downloadable audit JSON. Spatial and monthly-record counts remain separate. See [production](production.md) and run `node tests/browser/production_smoke.cjs` for the synthetic chart/attribution browser check.

A mutation started from another app session or CLI process now produces “Another workflow is running” and a wait/retry warning; the action history records Busy. Existing results remain readable. After a stopped process, the next mutation marks unfinished attempt history interrupted and verifies/reuses committed data. See [release verification and recovery](release_verification.md).
