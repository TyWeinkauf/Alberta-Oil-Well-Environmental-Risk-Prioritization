# Alberta waterways in the app

The supplied `alberta_hydro_postgis_import.zip` was reviewed as reference code. Its original province-wide `environment.*` tables are not read by this app. The adaptation uses the project's SQLAlchemy connection, source catalogue, immutable HTTP cache, contracts, quarantine, database-wide lock and atomic inventory snapshots. Package README commands were treated as reference, and its `.env`, requirements and bytecode were not copied over project files.

## Province-wide layer 72 and ST37 comparison

The province-wide path requests every published record from **Lake/River (20K), layer 72** using `where=1=1`. It includes the icefield, quarry and dugout codes omitted from the regional defaults. The scope is the polygon layer the user specified. Streams and intermittent waterbodies have their own layers. [Official layer-72 metadata](https://geospatial.alberta.ca/titan/rest/services/environment/base_water_feature/MapServer/72)

The 20 November 2026 live probe returned ten polygons from the user’s update-layer endpoint and wrote `data/raw/waterbodies_test.geojson` (96,572 bytes, SHA-256 `7cd179f6223fc9d2130fe7a25ce4cc9498b2f44d8f8724ad6c2139a07aa7d2f6`). The base layer reported **127,227 records**. Its ID list reconciled with that count and its first ten geometry records matched the requested IDs.

Developer diagnostics for the publisher endpoints are available through `scripts/test_water_api.py`.

```powershell
.\.venv\Scripts\python.exe scripts\test_water_api.py
.\.venv\Scripts\python.exe scripts\test_water_api.py --layer base --count-only
.\.venv\Scripts\python.exe scripts\test_water_api.py --layer base --verify-paging
```

### Import and compare

Configure the project's private `.env` with its actual `DATABASE_URL` and open **PostGIS workflows → Waterways → Alberta waterbodies, streams and ST37**.

1. Click **Import Alberta waterbodies** to load the full polygon layer. The app reports progress, selects the imported snapshot and shows polygon and quarantine counts.
2. Click **Import ST37 wells** to stage the retained workbook. Enter its documented geographic CRS and evidence in **Workbook coordinate evidence** when available. Leaving both fields blank stages the reported coordinates and well attributes. [ST37 staging](st37_excel.md#stage-well-information-before-environmental-analysis)
3. Select the stored waterbody and ST37 snapshots and click **Run waterbody comparison**. The comparison becomes available when the selected ST37 snapshot has documented coordinates and both snapshots have accepted records. Read the threshold summary and look up a specific well by licence number.

The import reads a publisher count and the corresponding complete ID list. It requests and validates a geometry page at a time, stages rows through PostgreSQL COPY, and verifies the ID list and available edit timestamp again before publication. Valid polygons and source properties go to `screening.water_features` in EPSG:3400. Rejected records and their source payloads go to `screening.water_feature_rejects`. Publication commits a single snapshot after all records are accounted for. An unchanged import reuses its ID. The source responses are traceable in the stored manifest and local HTTP cache. The comparison and app read from PostGIS. The default guard is 2 million records with 64 MiB per response and a 16 GiB cumulative transfer ceiling. The service may change records during a download. Count, ID and available edit metadata checks guard publication, and the manifest records the responses used.

Results are stored in `screening.st37_waterbody_proximity` and tied to both immutable import IDs by `screening.waterbody_comparisons`. PostGIS uses `ST_DWithin` to find accepted polygons within 500 m and `ST_Distance` to measure the nearest qualifying geometry. A well inside a polygon has distance zero. The summary reports inclusive matches at 50, 100, 250 and 500 m. If coverage is incomplete, unmatched wells have unknown results. Snapshot selections and licence searches read stored data. Each button runs the corresponding write action.

### Browse shuffled well batches

Open a stored comparison and use **Next batch** or **Previous batch** under **ST37 wells and water features**. The app shuffles the selected well snapshot for the session and splits it into non-overlapping batches of up to 10,000 points. The 541,190-well snapshot has 55 batches. The last batch contains 1,190 wells, and the controls wrap at either end. Switching between waterbody and stream comparisons for the same well snapshot keeps the same well batch.

The map draws each batch's well locations and the nearest accepted water features recorded within 500 m. Click a point for the original licence and its stored distance or coverage result. Water shapes are simplified for display. The full comparison supplies the summary counts and exact licence lookup.

On 23 November 2026, SQL and Edge checks against project PostGIS verified 10,000 points in batches 1 and 2 and 1,190 in batch 55, with no repeated wells across those batches. The browser rendered the same batch against stream lines and waterbody polygons. `python -m pytest -q` passed all 149 tests in a disposable PostGIS database.

### Project database status

The 20 November imports preserved raw ST37 snapshot `73363997-10a0-5817-9546-57cdf2b2b1a5` and layer-72 snapshot `9b833be4-ff85-5712-9b8a-7d34be2b761c`. Layer 72 accounts for all **127,227** publisher records as **127,189 valid polygons** and **38 quarantined records**. On 23 November the Streamlit buttons created projected ST37 snapshot `4bb2ac73-df0b-5698-9295-c86028ced168` and ran both provincial comparisons. The snapshot has **541,190 valid EPSG:3400 points** and preserves every licence, source coordinate and attribute from the raw import. [ST37 datum and release](st37_excel.md#verified-november-release-and-datum)

| Stored comparison | Within 50 m | Within 100 m | Within 250 m | Within 500 m | Unknown within 500 m |
| --- | ---: | ---: | ---: | ---: | ---: |
| Layer 72 waterbodies `3313a0f2-629c-54e9-9686-a9e0f8c3d27c` | 1,495 | 5,378 | 28,642 | 71,942 | 469,248 |
| Layer 107 streams `5be2b7cd-071c-5ce0-bd10-289a323238b0` | 1,831 | 7,390 | 27,380 | 57,367 | 483,823 |

Each comparison has one result per licence. The limits are inclusive and count observed matches in the accepted geometries. Both source snapshots record incomplete coverage, so unmatched wells remain unknown. An exact text lookup confirmed leading-zero licences in the stored results. [SQL reconciliation and comparison evidence](evidence/postgis_hydrography_2026-11-23.json)

All **149 tests passed** with a disposable PostgreSQL 17/PostGIS database. The Streamlit checks cover the import and comparison buttons, the threshold summary, a leading-zero licence lookup, failed-refresh recovery, datum gating and read-only reruns.

## Province-wide layer 107 streams

In the same Streamlit panel, click **Import Alberta streams**. This loads every published line record from **Stream (20K), layer 107** into an independent PostGIS snapshot. The live publisher count and reconciled ID list contained **143,570 records** on 20 November 2026, and the first ten records matched their requested IDs. Alberta publishes this line layer in NAD83 / Alberta 10-TM Forest with the Open Government Licence – Alberta. [Official layer-107 metadata](https://geospatial.alberta.ca/titan/rest/services/environment/base_water_feature/MapServer/107)

The live button import published snapshot `502120a2-a315-56ae-94ac-4d59ebc8963f`. PostGIS reconciled **143,568 LineStrings** and **two retained invalid geometry records** to the full publisher count. Coverage is labelled incomplete.

To compare streams with wells, select the stream snapshot as the **Alberta hydrography snapshot** and click **Run stream comparison** after choosing a datum-verified ST37 snapshot. The comparison evaluates perennial stream, canal, oxbow and ditch codes (`STR-PER`, `CANAL`, `OXBOW-PER`, `DITCH`) at the same four thresholds. The live count for those codes also totalled 143,570. All publisher attributes and validated lines remain in the inventory.

## Verified sources and selection

Official metadata and bounded queries were checked on **10 November 2026**. [Base Water Feature](https://geospatial.alberta.ca/titan/rest/services/environment/base_water_feature/MapServer) reports native EPSG:3400, GeoJSON support, and `OBJECTID`, `NAME`, `FEATURE_TYPE` fields. Layer metadata explicitly states the [Open Government Licence – Alberta](https://open.alberta.ca/licence). Metadata/response hashes, scopes and retrieval times are retained in [verification evidence](evidence/hydrography_2026-11-10.json).

| Layer | Use | Selected `FEATURE_TYPE` codes |
|---|---|---|
| [72: Lake/River (20K)](https://geospatial.alberta.ca/titan/rest/services/environment/base_water_feature/MapServer/72) | Default polygons | `LAKE-PER`, `RIV-MAJ`, `RESERVOIR`, `CANAL-MAJ`, `OXBOW-PER` |
| [107: Stream (20K)](https://geospatial.alberta.ca/titan/rest/services/environment/base_water_feature/MapServer/107) | Default lines | `STR-PER`, `CANAL`, `OXBOW-PER`, `DITCH` |
| [76: Intermittent Lake (20K)](https://geospatial.alberta.ca/titan/rest/services/environment/base_water_feature/MapServer/76) | Optional seasonal polygons | `LAKE-RECUR`, `OXBOW-RECUR` |
| [108: Intermittent Stream / Aqueduct / Spillway](https://geospatial.alberta.ca/titan/rest/services/environment/base_water_feature/MapServer/108) | Optional seasonal/indefinite flow lines and structures | `STR-RECUR`, `STR-INDEF`, `OXBOW-RECUR`, `AQUEDUCT`, `SPILLWAY` |

These are full-base layers, rather than update-only hydrography. Explicit predicates exclude arbitrary manual/DEM flow connectors and omit icefields, quarry and dugout polygons from the default selection. Map renderer symbols are not assumed to filter query results. This is a documented screening choice; excluded water types may still matter. Layer scale does not establish survey accuracy or a regulatory setback.

## Regional imports in Streamlit

Fill the project's ignored `.env` with actual PostgreSQL/PostGIS connection details, then run:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open **PostGIS workflows → Waterways → Import waterways**, then enable **Preview imported waterways**. The default imports `config/study_area.live.yml` (Drayton Valley) plus a projected **500 m margin**. **Include seasonal waterways** adds verified optional water sources. **Recheck water source updates** rechecks cached inputs. Preview shows actual lines and polygons, source codes and a downloadable manifest, with optional OpenStreetMap tiles.

The control works before an analyzed well dataset exists. Imports occur only on button clicks; preview rerenders never re-import/download. The water preview is independent of synthetic well results. The normal **Run full pipeline** action uses the same water catalogue entries when the remaining core sources are ready. A private `SOURCE_CATALOG_PATH` takes precedence; copy verified water entries into it deliberately if using one.

The preview retains the import selected by your last successful button action, including when switching back to an older cached base inventory after a seasonal import. The seasonal checkbox controls the independent inventory import. For seasonal sources in a full analytical run, explicitly enable those entries in your private source catalogue too.

The regional import guards against excess counts and fails without truncation. It applies the configured study area and feature-type selection.

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

The project database holds the provincial inventories and water-only comparisons above. The full multi-source screening workflow still needs verified protected-area and habitat inputs. [Data inventory](../aida-final-project-tyler-weinkauf/shared-resources/data-inventory.md) · [Design tracker](../DESIGN.md#remaining-work-in-order)
