# Alberta waterways in the app

The supplied `alberta_hydro_postgis_import.zip` was reviewed as reference code. Its original province-wide `environment.*` tables are not read by this app. The adaptation uses the project's SQLAlchemy connection, source catalogue, immutable HTTP cache, contracts, quarantine, database-wide lock and atomic inventory snapshots. Package README commands were treated as reference, and its `.env`, requirements and bytecode were not copied over project files.

## Verified sources and selection

Official metadata and bounded queries were checked on **10 November 2026**. [Base Water Feature](https://geospatial.alberta.ca/titan/rest/services/environment/base_water_feature/MapServer) reports native EPSG:3400, GeoJSON support, and `OBJECTID`, `NAME`, `FEATURE_TYPE` fields. Layer metadata explicitly states the [Open Government Licence – Alberta](https://open.alberta.ca/licence). Metadata/response hashes, scopes and retrieval times are retained in [verification evidence](evidence/hydrography_2026-11-10.json).

| Layer | Use | Selected `FEATURE_TYPE` codes |
|---|---|---|
| [72: Lake/River (20K)](https://geospatial.alberta.ca/titan/rest/services/environment/base_water_feature/MapServer/72) | Default polygons | `LAKE-PER`, `RIV-MAJ`, `RESERVOIR`, `CANAL-MAJ`, `OXBOW-PER` |
| [107: Stream (20K)](https://geospatial.alberta.ca/titan/rest/services/environment/base_water_feature/MapServer/107) | Default lines | `STR-PER`, `CANAL`, `OXBOW-PER`, `DITCH` |
| [76: Intermittent Lake (20K)](https://geospatial.alberta.ca/titan/rest/services/environment/base_water_feature/MapServer/76) | Optional seasonal polygons | `LAKE-RECUR`, `OXBOW-RECUR` |
| [108: Intermittent Stream / Aqueduct / Spillway](https://geospatial.alberta.ca/titan/rest/services/environment/base_water_feature/MapServer/108) | Optional seasonal/indefinite flow lines and structures | `STR-RECUR`, `STR-INDEF`, `OXBOW-RECUR`, `AQUEDUCT`, `SPILLWAY` |

These are full-base layers, rather than update-only hydrography. Explicit predicates exclude arbitrary manual/DEM flow connectors and omit icefields, quarry and dugout polygons from the default selection. Map renderer symbols are not assumed to filter query results. This is a documented screening choice; excluded water types may still matter. Layer scale does not establish survey accuracy or a regulatory setback.

## App and command line

Fill the project's ignored `.env` with actual PostgreSQL/PostGIS connection details, then run:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open **Waterways → Import waterways** in the sidebar, then enable **Preview imported waterways**. The default imports `config/study_area.live.yml` (Drayton Valley) plus a projected **500 m margin**. **Include seasonal waterways** adds verified optional water sources; **Recheck water source updates** rechecks cached inputs. Preview shows actual lines/polygons, source IDs/codes and a downloadable manifest, with optional OpenStreetMap tiles. Geometry can render offline after acquisition using cached inputs and vendored map assets.

The control works before an analyzed well dataset exists. Imports occur only on button clicks; preview rerenders never re-import/download. The water preview is independent of synthetic well results. The normal **Run full pipeline** action uses the same water catalogue entries when the remaining core sources are ready. A private `SOURCE_CATALOG_PATH` takes precedence; copy verified water entries into it deliberately if using one.

The preview retains the import selected by your last successful button action, including when switching back to an older cached base inventory after a seasonal import. The seasonal checkbox controls the independent inventory import. For seasonal sources in a full analytical run, explicitly enable those entries in your private source catalogue too.

```powershell
.\.venv\Scripts\python.exe scripts\import_hydrography.py
.\.venv\Scripts\python.exe scripts\import_hydrography.py --include-seasonal
.\.venv\Scripts\python.exe scripts\import_hydrography.py --include-seasonal --refresh
```

Options include `--catalog`, `--study-area` and `--max-records` (10,000/source by default, maximum 100,000). This command is bounded to the study area; it does not execute the ZIP's province-wide/sample-mirror workflow. Excess counts fail without truncation. No new runtime dependencies are needed.

## Storage and failure behavior

Migration `006_water_inventory.sql` adds `screening.water_imports` (scope, lineage, manifest, validation/quarantine and coverage) and `screening.water_features` (source key/ID, name, classification code, raw properties and valid EPSG:3400 geometry with a GiST index). The ArcGIS adapter uses verified HTTPS GET requests, bounded ID batches (default 200), count/ID/page reconciliation and explicit feature-code predicates. WGS84 GeoJSON is validated, projected and clipped to the study area plus 500 m. Raw response hashes/properties remain in immutable source bundles; object IDs are scoped to their layer/snapshot, not assumed permanent across releases.

All selected layers publish together. Acquisition, insertion or report-write failure rolls back the new inventory and preserves previous results. Unchanged inputs/settings reuse the import ID without duplicate rows. Refresh creates a new snapshot after successful completion, reflecting source changes/deletions without destructive in-place pruning. IDs shared by different layers remain distinct. Attempt history uses `screening.pipeline_attempts` with `water:*` stages. A water-only import creates no `pipeline_runs`, well rows or proximity bands.

Invalid records remain referenced in the manifest/raw bundles and make coverage **incomplete**. Expected outside-margin bounding-box candidates do not establish a coverage gap inside the study area. Preview data is cached by immutable import ID and database identity.

## Verification and remaining work

All **142 unit/PostGIS integration tests passed** on Windows PostgreSQL 17.11/PostGIS 3.6.2; edited-module type checks passed. A running Streamlit instance was driven through its agent API: initial load, actual import button, preview table/iframe and incomplete-coverage warning passed, with no new console warning/traceback. Tests cover raw properties, per-layer ID isolation, empty optional layers, no rerender imports, failed-refresh retention, rejected geometries and failed-load rollback.

Actual Drayton Valley imports were validated in a **separate temporary database**:

| Selection | Accepted | Quarantined | Coverage |
|---|---:|---:|---|
| Default waterbodies + streams | 33 (5 polygons, 28 lines) | 1 | Incomplete |
| Including seasonal layers | 121 (5 polygons, 116 lines) | 1 | Incomplete |

Repeats reuse the same IDs/counts. SQL verifies valid EPSG:3400 geometry, zero arbitrary flow connectors and zero published screening runs. Rejected layer-72 `OBJECTID=249048`, `RIV-MAJ` has a source ring self-intersection. It is quarantined without silent repair. Its absence is not evidence that no river is nearby; coverage stays incomplete until the gap is defensibly resolved.

The user's database is unmodified because `.env` still contains connection placeholders. Full screening still needs AER datum/provenance and protected-area/habitat inputs. This work does not establish Alberta-wide completion, complete river coverage or final course findings. See the [data inventory](../aida-final-project-tyler-weinkauf/shared-resources/data-inventory.md) and [design tracker](../DESIGN.md).
