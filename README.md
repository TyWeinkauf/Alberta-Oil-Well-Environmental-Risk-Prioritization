# Alberta Oil Well Environmental Screening

Educational training project for **AIDA 1145 (Data Engineering)** and **AIDA 2362 (GIS)**. It will prepare permitted well/environmental data and present transparent proximity screening. Proximity does not establish contamination, environmental harm or regulatory compliance. Do not use this project for operational decisions.

The existing course workspace is preserved in [aida-final-project-tyler-weinkauf/](aida-final-project-tyler-weinkauf/README.md). See [DESIGN.md](DESIGN.md#13-phased-codex-implementation-plan) for scope and live progress tracking.

The completed application will use **real AER wells, Alberta surface water, Alberta parks/protected areas and federal critical habitat**, with OpenStreetMap as the basemap. Alberta wetlands are an optional additional factor; the 2014 ESA layer is an optional historical comparison. The [user-supplied dataset reference](docs/dataset_reference.md) records these sources and their CRS/licensing cautions. Synthetic fixtures verify the implementation before live ingestion; they are not the final project dataset. Petrinex production remains a separate planned milestone in the design.

## What works now

Phases 0–2 provide validated configuration, transactional PostGIS migrations, an offline synthetic seed, quarantine reasons, raw-snapshot checksums, nearest-feature distance calculations, category/threshold classification and JSON reports. The demo contains **2 accepted wells, 2 accepted environmental features and 6 quarantined records**. Repeating it uses the same run and does not duplicate rows.

There is no project web UI, live downloader or production ingestion yet. The ingestion run remains **seeded**; the separate spatial report has status **analyzed**. Streamlit is installed for the next phase.

## Managed cloud quick start

Use the existing checkout; cloud tasks are already isolated. From its root:

```bash
source /workspace/alberta-environment/activate.sh
bash /workspace/alberta-environment/start-db.sh
python scripts/setup_db.py
python scripts/demo_seed.py
python scripts/demo_seed.py  # Same run ID and row counts
python scripts/analyze_demo.py  # Default: synthetic water screening, 500 m threshold
pytest -q tests/unit
```

The cloud database uses a local Unix socket and exposes no TCP port. Do not replace the injected `DATABASE_URL` with the example Windows URL. Helper files live outside Git in `/workspace/alberta-environment`; the project code and fixtures are in this repository.

## Windows setup (PowerShell)

These steps target **Python 3.12, PostgreSQL 17 and PostGIS 3.5**. The implementation has been tested on Linux; the Windows instructions have not been executed on a Windows machine.

1. Install Python 3.12 with the Windows Python launcher. Install PostgreSQL 17 and its matching PostGIS extension using the PostgreSQL installer/Stack Builder. Keep the PostgreSQL password you choose in your local password manager.
2. Open pgAdmin, connect to your local PostgreSQL server and create a database named `alberta_risk` (right-click **Databases → Create → Database**). The setup script enables PostGIS; use a local database role permitted to create the extension and schema. A database administrator can enable PostGIS first if needed.
3. Open PowerShell in the repository root, then run:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

4. In `.env`, replace `CHANGE_ME` with the password for your **local** PostgreSQL role. Match the role, database and port to your installation. URL-encode special password characters (for example, `@` becomes `%40`). Keep `.env` private; it is ignored by Git. An already-set `DATABASE_URL` environment variable takes precedence over `.env`.
5. Run the migration and demo:

```powershell
.\.venv\Scripts\python.exe scripts\setup_db.py
.\.venv\Scripts\python.exe scripts\demo_seed.py
.\.venv\Scripts\python.exe scripts\demo_seed.py
.\.venv\Scripts\python.exe scripts\analyze_demo.py
.\.venv\Scripts\python.exe -m pytest -q tests\unit
```

Setup applies pending migrations (`001_initial.sql`, `002_spatial_coverage.sql`); subsequent setup reports `none (already current)`. The seed prints a stable run ID and counts of 2 wells, 2 environmental features, 6 quarantine records and 0 production rows. Proximity rows start at 0; analysis stores 10 (one per well/category) and unchanged reseeding preserves them. Read `outputs/runs/<run_id>/manifest.json`, `validation.json` and `analysis.json`. No source download or basemap request is needed.

The default analysis selects water: the wells are 50 m and 150 m from the synthetic stream. Its threshold sensitivity report changes matches from 2 at 500 m to 1 at 50 m. For another selection:

```bash
python scripts/analyze_demo.py --threshold 50
python scripts/analyze_demo.py --categories water protected_area
```

The protected-area demo layer is incomplete because one polygon was quarantined. Selecting it makes the exact overall band unknown; that is different from no nearby feature. See [spatial methodology](docs/spatial_methodology.md) for coverage, cumulative flags and category selection rules. The clean boundary test fixture validates complete-category minima and exact distance boundaries.

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

## Files and next work

- [Architecture](docs/architecture.md): components, transaction boundaries and planned phases.
- [Data dictionary](docs/data_dictionary.md): tables, fields and fixture accounting.
- [Limitations](docs/limitations.md): synthetic data, source verification and attribution boundaries.
- [Spatial methodology](docs/spatial_methodology.md): nearest-feature calculations, coverage states and sensitivity evidence.
- `config/`: demo study extent and disabled, unverified live-source placeholders.
- `sql/migrations/`, `src/`, `scripts/`, `tests/`: implementation and repeatable checks.

Raw data, caches, reports, virtual environments and credentials are ignored. Small project-authored fixtures in `tests/fixtures/` are intentionally versioned. Add a new migration instead of editing one already applied. Phase 3 will add the Streamlit map. Live source URLs, fields, licensing and the first real study region still require verification in Phase 4.
