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

Configure `DATABASE_URL` in the project's private `.env` or environment. Run the import commands when a provincial snapshot is needed.

1. Run `python scripts/import_waterbodies.py` for the polygon inventory or `python scripts/import_waterbodies.py --layer streams` for the stream inventory. Each command prints the snapshot ID, accepted count and quarantine count.
2. Stage the workbook with its documented geographic CRS and evidence. `scripts/import_st37.py` prints the full well snapshot ID. [ST37 staging](st37_excel.md#stage-well-information-before-environmental-analysis)
3. Run `python scripts/compare_st37_waterbodies.py --st37-import-id WELL_UUID --water-import-id WATER_UUID` using the two snapshot IDs. The command stores and summarizes the comparison. In Streamlit, open **ST37 well inventory → Water proximity map** to browse it.

The import reads a publisher count and the corresponding complete ID list. It requests and validates a geometry page at a time, stages rows through PostgreSQL COPY, and verifies the ID list and available edit timestamp again before publication. Valid polygons and source properties go to `screening.water_features` in EPSG:3400. Rejected records and their source payloads go to `screening.water_feature_rejects`. Publication commits a single snapshot after all records are accounted for. An unchanged import reuses its ID. The source responses are traceable in the stored manifest and local HTTP cache. The comparison and app read from PostGIS. The default guard is 2 million records with 64 MiB per response and a 16 GiB cumulative transfer ceiling. The service may change records during a download. Count, ID and available edit metadata checks guard publication, and the manifest records the responses used.

Results are stored in `screening.st37_waterbody_proximity` and tied to both immutable import IDs by `screening.waterbody_comparisons`. PostGIS uses `ST_DWithin` to find accepted polygons within 500 m and `ST_Distance` to measure the nearest qualifying geometry. A well inside a polygon has distance zero. The summary reports inclusive matches at 50, 100, 250 and 500 m. If coverage is incomplete, unmatched wells have unknown results. Snapshot selections and licence searches read stored data.

### Browse shuffled well batches

Open **ST37 well inventory → Water proximity map** and choose an **Imported water layer**. **Buffer distance** selects 50, 100, 250 or 500 m. The map starts at 500 m, showing wells with an observed distance at or below that value. PostgreSQL applies the filter before choosing the shuffled batch. Use **Next batch** or **Previous batch** to cycle through groups of up to 10,000 wells. The page resets when you change the matching buffer or water layer.

Uncheck **Only show wells within the buffer** to browse all 541,188 mappable positions in 55 batches. The same unfiltered batch stays in view when you switch layers. Threshold summaries count the full 541,190-well comparison, including the two records flagged by the boundary audit. [Boundary check and coordinate accuracy](st37_excel.md#alberta-boundary-and-distance-accuracy)

The map draws each batch's well locations and the nearest accepted water features recorded within 500 m. The legend on the right explains the well colors and identifies the teal water features. Click a point for its licence, water feature and stored distance or coverage result. An exact licence search shows the selected well and its buffer at the chosen radius, regardless of its distance to water. Map geometries are displayed in WGS84, and water shapes are simplified for display with a 25 m tolerance. PostGIS measures distances on the full accepted geometry in EPSG:3400.

On 23 November 2026, Edge loaded OpenStreetMap tiles, cycled from the first batch to the last and back, and showed the same well position for licence `0321984` on both water layers. The stored distances of **195.26 m to Checker Lake** and **199.29 m to the Gregoire River** matched an independent PostGIS `ST_Distance` calculation using the imported geometries.

On 24 November 2026, read-only queries verified buffer counts at all four distances. The audited map contains 57,367 stream matches and 71,941 waterbody matches at 500 m. One of the waterbody matches in the full comparison falls outside the Alberta boundary. Edge verified the buffer changes, two non-overlapping 10,000-point stream batches and the buffer around an exact licence result.

### Project database status

The 20 November imports preserved raw ST37 snapshot `73363997-10a0-5817-9546-57cdf2b2b1a5` and layer-72 snapshot `9b833be4-ff85-5712-9b8a-7d34be2b761c`. Layer 72 accounts for all **127,227** publisher records as **127,189 valid polygons** and **38 quarantined records**. On 23 November the Streamlit buttons created projected ST37 snapshot `4bb2ac73-df0b-5698-9295-c86028ced168` and ran both provincial comparisons. The snapshot has **541,190 valid EPSG:3400 points** and preserves every licence, source coordinate and attribute from the raw import. [ST37 datum and release](st37_excel.md#verified-november-release-and-datum)

| Stored comparison | Within 50 m | Within 100 m | Within 250 m | Within 500 m | Unknown within 500 m |
| --- | ---: | ---: | ---: | ---: | ---: |
| Layer 72 waterbodies `3313a0f2-629c-54e9-9686-a9e0f8c3d27c` | 1,495 | 5,378 | 28,642 | 71,942 | 469,248 |
| Layer 107 streams `5be2b7cd-071c-5ce0-bd10-289a323238b0` | 1,831 | 7,390 | 27,380 | 57,367 | 483,823 |

Each comparison has one result per licence. The limits are inclusive and count observed matches in the accepted geometries. Both source snapshots record incomplete coverage, so unmatched wells remain unknown. An exact text lookup confirmed leading-zero licences in the stored results. [SQL reconciliation and comparison evidence](evidence/postgis_hydrography_2026-11-23.json)

All **149 tests passed** with a disposable PostgreSQL 17/PostGIS database. The Streamlit checks cover the import and comparison buttons, the threshold summary, a leading-zero licence lookup, failed-refresh recovery, datum gating and read-only reruns.

## Province-wide layer 107 streams

Run `python scripts/import_waterbodies.py --layer streams` to load **Stream (20K), layer 107** into an independent PostGIS snapshot. The live publisher count and reconciled ID list contained **143,570 records** on 20 November 2026, and the first ten records matched their requested IDs. Alberta publishes this line layer in NAD83 / Alberta 10-TM Forest with the Open Government Licence – Alberta. [Official layer-107 metadata](https://geospatial.alberta.ca/titan/rest/services/environment/base_water_feature/MapServer/107)

The live button import published snapshot `502120a2-a315-56ae-94ac-4d59ebc8963f`. PostGIS reconciled **143,568 LineStrings** and **two retained invalid geometry records** to the full publisher count. Coverage is labelled incomplete.

Pass the stream snapshot ID as `--water-import-id` when running `scripts/compare_st37_waterbodies.py`. The comparison evaluates perennial stream, canal, oxbow and ditch codes (`STR-PER`, `CANAL`, `OXBOW-PER`, `DITCH`) at the same four thresholds. The live count for those codes also totalled 143,570. All publisher attributes and validated lines remain in the inventory.

## Verified sources and selection

Official metadata and bounded queries were checked on **10 November 2026**. [Base Water Feature](https://geospatial.alberta.ca/titan/rest/services/environment/base_water_feature/MapServer) reports native EPSG:3400, GeoJSON support, and `OBJECTID`, `NAME`, `FEATURE_TYPE` fields. Layer metadata explicitly states the [Open Government Licence – Alberta](https://open.alberta.ca/licence). Metadata/response hashes, scopes and retrieval times are retained in [verification evidence](evidence/hydrography_2026-11-10.json).

| Layer | Use | Selected `FEATURE_TYPE` codes |
|---|---|---|
| [72: Lake/River (20K)](https://geospatial.alberta.ca/titan/rest/services/environment/base_water_feature/MapServer/72) | Default polygons | `LAKE-PER`, `RIV-MAJ`, `RESERVOIR`, `CANAL-MAJ`, `OXBOW-PER` |
| [107: Stream (20K)](https://geospatial.alberta.ca/titan/rest/services/environment/base_water_feature/MapServer/107) | Default lines | `STR-PER`, `CANAL`, `OXBOW-PER`, `DITCH` |
| [76: Intermittent Lake (20K)](https://geospatial.alberta.ca/titan/rest/services/environment/base_water_feature/MapServer/76) | Optional seasonal polygons | `LAKE-RECUR`, `OXBOW-RECUR` |
| [108: Intermittent Stream / Aqueduct / Spillway](https://geospatial.alberta.ca/titan/rest/services/environment/base_water_feature/MapServer/108) | Optional seasonal/indefinite flow lines and structures | `STR-RECUR`, `STR-INDEF`, `OXBOW-RECUR`, `AQUEDUCT`, `SPILLWAY` |

These are full-base layers, rather than update-only hydrography. Explicit predicates exclude arbitrary manual/DEM flow connectors and omit icefields, quarry and dugout polygons from the default selection. Map renderer symbols are not assumed to filter query results. This is a documented screening choice; excluded water types may still matter. Layer scale does not establish survey accuracy or a regulatory setback.

## Regional imports

Fill the project's ignored `.env` with actual PostgreSQL/PostGIS connection details, then run:

```powershell
.\.venv\Scripts\python.exe scripts\import_hydrography.py
```

The default region is Drayton Valley plus a projected 500 m margin. Use `--include-seasonal` to add verified optional sources, `--refresh` to recheck cached inputs, or `--study-area` to choose a region definition. The verified multi-source pipeline uses the configured catalogue when all its required sources are ready. [Source configuration](data_access.md)

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
