# Alberta Oil Well Environmental Screening

Educational training project for **AIDA 1145 (Data Engineering)** and **AIDA 2362 (GIS)**. It will prepare permitted well/environmental data and present transparent proximity screening. Proximity does not establish contamination, environmental harm or regulatory compliance. Do not use this project for operational decisions.

The existing course workspace is preserved in [aida-final-project-tyler-weinkauf/](aida-final-project-tyler-weinkauf/README.md). See [DESIGN.md](DESIGN.md#13-phased-codex-implementation-plan) for scope and live progress tracking.

**Classroom preview — 20 November 2026.** The default Streamlit mode reads a small local package of actual AER ST37 records. Choose Red Deer, Drayton Valley or Both, then filter, inspect and export the selected wells. The retained package has 28 wells per region and runs without a database connection. The illustrative map and simulated distances for these wells require verification of the workbook datum. [Classroom launch and preparation](docs/classroom_demo.md#launch-the-classroom-mode)

The retained all-real pipeline targets AER wells, Alberta surface water, protected areas and federal critical habitat, with optional wetlands/historical ESA and OpenStreetMap display. It remains separate from simulated classroom results. The [dataset reference](docs/dataset_reference.md) records intended real sources and licensing cautions. Petrinex/monthly production remains outside scope.

## What works now

**Alberta hydrography and ST37 — 20 November 2026.** In Streamlit, open **PostGIS workflows → Waterways → Alberta waterbodies, streams and ST37**. The three import buttons loaded 541,190 ST37 records, 127,189 valid layer-72 polygons and 143,568 valid layer-107 lines. PostGIS retains 38 polygon and two stream geometry rejects. Actual-well comparisons require verified workbook datum evidence. [Ordered completion checklist](DESIGN.md#remaining-work-in-order) · [Import and comparison](docs/hydrography.md#province-wide-layer-72-and-st37-comparison)

**Waterways update, 10 November 2026:** open **Waterways → Import waterways** in the app sidebar, then **Preview imported waterways**. Verified official waterbody polygons/stream lines are imported for the study area plus 500 m; seasonal sources are optional. Actual validation: 33 default or 121 seasonal features, one invalid polygon quarantined, all 142 tests/type checks and running-app checks pass. Your database needs actual `.env` values. See [waterways setup and quality details](docs/hydrography.md).

The retained ST37 workbook contains 541,190 distinct licences, with leading zeros preserved and six date-warning records. The app can reuse its audited preparation when staging it. [Excel preparation and inventory staging](docs/st37_excel.md)

Phases 0–3 provide validated configuration, transactional PostGIS migrations, an offline synthetic seed, quarantine reasons, raw-snapshot checksums, spatial analysis and a Streamlit map with persistent well selection, filters, matching exports, data quality and session history. The demo contains **2 accepted wells, 2 accepted environmental features and 6 quarantined records**. Repeating it uses the same run and does not duplicate rows.

The Phase 4 acquisition framework is implemented and tested with simulated sources, but official endpoint/schema/licence verification and an actual regional run are **in progress**; official service/download hosts still need access. Optional legacy production code remains in the repository, but Petrinex access is no longer a project milestone. Demo ingestion remains **seeded** and its spatial report is **analyzed**; a fully acquired and validated live run will use **succeeded**. The UI labels demo versus real-source mode explicitly.

## Managed cloud quick start

For the database-backed workflows, select **PostGIS workflows** in the app sidebar after launch.

Use the existing checkout; cloud tasks are already isolated. From its root:

```bash
source /workspace/alberta-environment/activate.sh
bash /workspace/alberta-environment/start-db.sh
streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
```

The cloud database uses a local Unix socket and exposes no TCP port. Do not replace the injected `DATABASE_URL` with the example Windows URL. Helper files live outside Git in `/workspace/alberta-environment`; the project code and fixtures are in this repository.

## Windows setup (PowerShell)

These steps target **Python 3.12 and PostgreSQL 17 with PostGIS**. The importer and all 136 unit/database tests passed on Windows PostgreSQL 17.11/PostGIS 3.6.2 on 10 November 2026 using a project virtual environment based on the bundled Python runtime. The standard Python-installer/launcher instructions below and a final user-database/app handoff still need verification.

1. Install Python 3.12 with the Windows Python launcher. Install PostgreSQL 17 and its matching PostGIS extension using the PostgreSQL installer/Stack Builder. Keep the PostgreSQL password you choose in your local password manager.
2. Open pgAdmin, connect to your local PostgreSQL server and create a database named `alberta_risk` (right-click **Databases → Create → Database**). The setup script enables PostGIS; use a local database role permitted to create the extension and schema. A database administrator can enable PostGIS first if needed.
3. Open PowerShell in the repository root, then run:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

4. In `.env`, replace `CHANGE_ME` with the password for your **local** PostgreSQL role. Match the role, database and port to your installation. URL-encode special password characters (for example, `@` becomes `%40`). Keep `.env` private; it is ignored by Git. An already-set `DATABASE_URL` environment variable takes precedence over `.env`.
5. Launch Streamlit:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The app applies pending migrations when you click an import or **Use demo dataset**. The synthetic database fixture has a stable run ID, 2 accepted wells, 2 environmental features and 6 spatial quarantine records. The app shows its stored results and can export selection evidence. Run reports are recorded under `outputs/runs/<run_id>/`.

The default analysis selects water. The wells are 50 m and 150 m from the synthetic stream. In the sidebar, set the distance threshold from 500 m to 50 m to change the count from 2 to 1.

The protected-area demo layer is incomplete because one polygon was quarantined. Selecting it makes the exact overall band unknown; that is different from no nearby feature. See [spatial methodology](docs/spatial_methodology.md) for coverage, cumulative flags and category selection rules. The clean boundary test fixture validates complete-category minima and exact distance boundaries.

In the app, choose **PostGIS workflows** and then **Use demo dataset** to run setup, ingestion and analysis for the synthetic database fixture. Click a map marker or use **Inspect a well** for details. Apply filters and download matching CSV, GeoJSON, map HTML or the manifest. Data quality and Run history show provenance, rejected inputs and workflow status. Live acquisition requires verified enabled catalogue entries and coverage notes.

Offline geometry and map exports require no CDN: small Leaflet/jQuery assets are vendored with licenses. **Show OpenStreetMap basemap (online)** is optional and requires `tile.openstreetmap.org`. The tile domain is now allowed by the published cloud policy and a fresh tile request returned HTTP 200. Some actual analytical service/download hosts remain inaccessible from this cloud session; access may differ on your machine. Offline rendering and interaction remain available. See [UI workflow](docs/ui_workflow.md).

For a regular Linux/macOS checkout, use `python3.12 -m venv .venv`, `source .venv/bin/activate`, `python -m pip install -r requirements.txt`, and the same Python script commands after configuring local PostgreSQL/PostGIS and `.env`.

## Database integration tests

Unit tests run without a database. Integration tests require a **separate empty database** whose name ends in `_test`. Create `alberta_risk_test` in pgAdmin, then supply its connection URL using a role permitted to create PostGIS and schemas. Do not use the application database.

```powershell
$env:TEST_DATABASE_URL = 'postgresql+psycopg://postgres:YOUR_URL_ENCODED_PASSWORD@localhost:5432/alberta_risk_test'
.\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:TEST_DATABASE_URL
```

For the prepared cloud machine, `alberta_risk_test` has already been created:

```bash
export TEST_DATABASE_URL='postgresql+psycopg://postgres@/alberta_risk_test?host=/workspace/alberta-environment/run/postgresql'
pytest -q --junitxml=outputs/test-results.xml
```

Each integration test refuses an existing `screening` schema, creates its own and drops that schema afterward. Run these tests sequentially. Without `TEST_DATABASE_URL`, integration tests are reported as **skipped**, not passed. See [reproducibility](docs/reproducibility.md) for evidence and clean-run checks.

With the app running, the managed environment can also run `node tests/browser/ui_smoke.cjs`. This uses Playwright/Chromium, blocks remote HTTP requests, and exercises actual marker clicks, filter persistence, download parity and standalone HTML. Node/Playwright are optional browser-test tools, not app runtime requirements. Another development machine must install those test tools and set `CHROMIUM_PATH` if needed.

## Files and next work

- [Architecture](docs/architecture.md): components, transaction boundaries and planned phases.
- [Data dictionary](docs/data_dictionary.md): tables, fields and fixture accounting.
- [Limitations](docs/limitations.md): synthetic data, source verification and attribution boundaries.
- [Spatial methodology](docs/spatial_methodology.md): nearest-feature calculations, coverage states and sensitivity evidence.
- [Source verification](docs/source_verification.md): Phase 4 status, observed cloud access failures and acquisition commands.
- [Data access routes](docs/data_access.md): runtime APIs/downloads and configured local-file ingestion.
- [UI workflow](docs/ui_workflow.md): map interaction, offline/online modes, exports and browser checks.
- `config/`: demo study extent and disabled, unverified live-source placeholders.
- `sql/migrations/`, `src/`, `scripts/`, `tests/`: implementation and repeatable checks.

Raw data, caches, reports, virtual environments and credentials are ignored. Small project-authored fixtures in `tests/fixtures/` are intentionally versioned. Add a new migration instead of editing one already applied. Remaining source work is to verify actual fields, CRS, licensing and coverage, finish any source-specific transformations, and validate a real study-region run. The dataset reference remains the intended final-data scope.

## Phase 4 in progress: real-source acquisition

The HTTP cache, ArcGIS ID-batch adapter, GIS file reader, 500 m environmental margin and atomic PostGIS workflow are implemented. Official water endpoints and bounded imports have been verified, and the full multi-source pilot remains open.

Published discovery permissions now allow provincial catalogue, ArcGIS portal and Petrinex documentation requests. Some actual service/download hosts still fail in this cloud session; these observations do not determine access from your own runtime. The program can acquire verified configured HTTP downloads and ArcGIS APIs. Import of user-downloaded GeoJSON/GIS, coordinate-mapped well CSV and production CSV/ZIP is implemented (steps 4.2c/5.2c). Use a verified custom catalogue through `--catalog` or `SOURCE_CATALOG_PATH`. See [data access routes](docs/data_access.md) for current support and remaining work.

[Source verification status](docs/source_verification.md) explains the remaining endpoint, licence, CRS and field-mapping checks. The configurable pilot is `config/study_area.live.yml` (Drayton Valley). **Run full pipeline** becomes available when all core source entries are verified and configured.

## AER wells and environmental inputs — current scope

Petrinex and monthly production are excluded from the current project. The app focuses on AER surface-well locations/identifiers, licensee, available legal location and licence attributes, plus proximity to water, protected areas and critical habitat. ST37's production-string layer is well/string metadata, not monthly volumes. The default source catalogue and local template no longer include Petrinex, and the default app has no production controls/chart. Previously implemented production code/tables remain optional legacy functionality; existing data/migration history is preserved.

Every user must download permitted source files themselves. The entire `data/` directory is ignored by Git. Put originals under `data/raw/`, configure a private catalogue, and let the project pipeline create its normalized PostGIS tables and proximity results. Raw publisher datasets are not bundled on GitHub. See [the download checklist](docs/download_inputs.md), [ST37 guide review](docs/st37_reference.md) and [runtime input configuration](docs/data_access.md).

Use **Import ST37 wells** for the retained surface-hole Excel workbook. For an optional geodatabase ZIP, use regional preparation to inspect the original and create a bounded study-area package under the app's 512 MiB and 10,000-record defaults.

Moving to a local project folder: the [download checklist](docs/download_inputs.md) now centralizes all publisher/service links, the exact listed download format where confirmed, and the remaining local setup, mapping, extraction, PostGIS and acceptance steps. Actual water/parks vector export availability is still to be confirmed; REST is a separate supported route.

## Prepare a regional extract from a large download

Point the private catalogue's `local_path` at the original ZIP or `.gdb`, then inspect it before setting actual layer/CRS/field mappings and provenance:

```bash
python scripts/prepare_extract.py --catalog data/raw/imports/catalog.yml --source aer_wells --inspect
python scripts/prepare_extract.py --catalog data/raw/imports/catalog.yml --source aer_wells --study-area config/study_area.live.yml
```

Set `SOURCE_CATALOG_PATH` to the generated catalogue and click **Run full pipeline** in Streamlit when the required sources are ready.

Preparation retains only the selected layer/fields and regional candidates, includes a 500 m margin for environmental sources, records original input checksums and refuses truncation or incompatible scope reuse. It preserves verification flags and other catalogue entries; all required sources must still be ready before ingestion. Read [regional extract instructions](docs/regional_extracts.md) for limits, original-file handling and configuration steps. The full suite now passes **128 tests**, including prepared-package PostGIS ingestion and failure retention. No actual ST37 release has been loaded.

## Release verification and recovery

A database-wide advisory lock rejects duplicate mutation workflows across app sessions/CLI processes; reads remain available. A stopped process releases its lock, and the next mutation marks unfinished attempt history interrupted without deleting committed results. [Release verification](docs/release_verification.md) records the previous candidate's 118-test/new-environment and browser evidence; the new wells/environment scope is checked separately. Official input mappings and a real-data run remain open.

Separate candidate evidence indexes identify methods and remaining deliverables for [AIDA 1145](aida-final-project-tyler-weinkauf/courses/AIDA-1145/EVIDENCE.md) and [AIDA 2362](aida-final-project-tyler-weinkauf/courses/AIDA-2362/EVIDENCE.md).
