# Red Deer and Drayton Valley classroom demo

**Status — 23 November 2026.** The offline Streamlit demo reads a 174,514-byte package with 56 actual November ST37 wells, 69 imported water features and eight synthetic features in other categories. The water distances use the downloaded Alberta Lake/River and Stream geometries. [Workbook datum verification](st37_excel.md#verified-november-release-and-datum) · [Water snapshot provenance](hydrography.md#project-database-status)

Reference archive SHA-256: `cd3bb2b438775ec346d294745651907122789ee85896a95d242c514c75040a53`. The original Word design remains a reference; DESIGN.md remains the maintained project design.

## Agreed direction and interpretation

The primary demonstration covers **Red Deer and Drayton Valley**, using **actual ST37 surface-hole locations and downloaded Alberta waterways**. Wetlands, protected areas, habitat and significance areas are labelled synthetic. The classroom app reads the prepared extract locally.

**Course handoff clarification, 20 November 2026.** Use the course briefs already in the repository. The user selected Streamlit/Folium with an optional OpenStreetMap basemap to demonstrate GIS tasks. Show layer toggles, click-to-identify, metre-based buffers, a baseline and changed-threshold comparison, and an accessible map with matching table and exports. Document the projected CRS and how to reproduce the results offline. The preserved AIDA 2362 brief specifies QGIS. The Streamlit approach reflects the user's understanding of acceptable tooling, with instructor confirmation unverified. [AIDA 1145 brief](../aida-final-project-tyler-weinkauf/courses/AIDA-1145/README.md) · [AIDA 2362 brief](../aida-final-project-tyler-weinkauf/courses/AIDA-2362/README.md)

The supplied `oilwell_environment_codex_starter.zip` is a reference, not a replacement project. Its `AGENTS.md`, README, start-here document, source/contract configuration, source-workflow/ST37 notes, synthetic generator, app and analysis SQL were inspected without executing the package. The ZIP's own demo invents both wells and surroundings: its included manifest reports 56 synthetic wells, 22 synthetic features and eight analytical categories. Those are starter-package claims, not newly verified outputs of this repository. Its `oilrisk` commands, database schema and source URLs must not be copied into this project as if already supported/verified.

The main showcase retains actual ST37 well IDs, positions and supplied attributes. New water distances use the same provincial imports as the opt-in PostGIS workflow. The original classroom package with synthetic water remains available by setting `CLASSROOM_DEMO_PATH` to `data/demo/classroom/demo.json`.

The earlier synthetic-water package keeps its illustrative banner and export wording.

> Illustrative classroom demo: real AER ST37 well locations with synthetic environmental features. Distances and proximity bands describe the simulated features only. They do not describe actual environmental conditions, contamination, legal setbacks or the risk of these real wells.

This deliberately labelled illustrative mode is separate from both the existing fully synthetic regression fixture and an all-real screening run. A network/source failure must never silently replace real environmental data with invented features.

## Earlier implementation evidence

| Existing evidence | Implication for the demo |
|---|---|
| Actual ST37 Excel inspected; 541,190 unique licence records, 11 preserved fields, leading zeros retained | Reuse the retained inventory; do not download another well dataset or replace real wells with the starter's invented wells. |
| Full inventory, Drayton Valley candidate CSV, raw checksums, date warnings and provenance retained locally | Prepare small derived regional packages without modifying the full inventory or original workbook. |
| Full ST37 load/repeat tested in a disposable database; six date-warning records reported | Importer behavior is proved. This does not prove the user's permanent database is populated. |
| Streamlit map, stable well selection, licence/company filters, details, exports and metre-based threshold logic tested | Reuse the working components through a small offline dataset adapter. |
| Vendored Leaflet/jQuery assets and no-tile rendering already work | Preserve these; the starter's default online tiles/plugins would not improve offline reliability. |
| Bounded real-water import/preview and raw-property lineage implemented | Preserve as optional real-source functionality. It is not a prerequisite for the synthetic-environment classroom path. |
| Earlier runtime verification: 142 unit/PostGIS tests plus type/running-app checks | Baseline for the original PostGIS app. The released classroom dataset has its own verification below. |

The app starts in **Classroom demo**. Switch to **ST37 well inventory** to browse the full workbook and inspect its stored water comparisons. [Streamlit and command-line workflows](ui_workflow.md)

## Well preservation and regional display

Retain these existing inputs unchanged:

- `aida-final-project-tyler-weinkauf/courses/AIDA-1145/data/ST37_SH.xlsx` — 38,596,313 bytes; SHA-256 `5b7139f06817b3458689bb82a3219c963165e3e671373e493222d948bb08e4f4`.
- `data/raw/st37/7b77926624ee1c2c7fb554d8426eab5ac5b1c6a17d7226fce6429cd2b3c1d8f4/inventory.csv` and its report — all 541,190 records; inventory SHA-256 `acee23f2655e8036aa9bc6d34d45c153328b534602e3f05ed1307d7417c3251e`.
- Existing snapshots, quarantine/warnings, water inventories and any user database records. No DROP, TRUNCATE, in-place replacement or full reload is needed for this demo.

A read-only scan of that inventory on 10 November found:

| Region | WGS84 bounding box `[west, south, east, north]` | Candidates | Sample |
|---|---|---:|---:|
| Red Deer | `[-113.88, 52.22, -113.74, 52.32]` | 105 | 28 |
| Drayton Valley | `[-115.08, 53.20, -114.94, 53.30]` | 477 | 28 |
| Both | Two separate rectangles, not their combined enclosing rectangle | 582 | 56 |

The Drayton rectangle preserves the existing pilot. The Red Deer rectangle centers the classroom study area. With the verified November workbook CRS (EPSG:4269), preparation transforms the original coordinates to WGS84 for region membership and uses EPSG:3400 for metre distances. Datum-aware counts are 105 for Red Deer and 477 for Drayton Valley. [Workbook datum verification](st37_excel.md#verified-november-release-and-datum)

The 28-per-region limit is a presentation setting in `config/demo_regions.yml`. Preparation ranks eligible original licence IDs by seeded SHA-256 per region, independent of the synthetic feature generator. The app reports candidate, sampled and visible counts. The package keeps selected IDs, workbook values, warning annotations and source hashes.

Preparation reads the retained CSV beside its ST37 report. The teacher's runtime reads the small package.

## Implementation

| Component | Classroom role |
|---|---|
| `src/demo/regions.py`, `config/demo_regions.yml` | Validate bounds, cap regional membership and select deterministic licence samples. |
| `scripts/prepare_classroom_demo.py`, `src/demo/data.py` | Validate input hashes, publish the portable package atomically, and adapt the selected region or Both to the shared dashboard model. |
| `src/demo/spatial.py` | Generate seeded scenario geometry with a 500 m regional margin, calculate metre distances and apply the shared threshold rules. |
| `app.py`, `src/ui/classroom.py` | Route before database preflight. Show the source preview or the illustrative scenario depending on package readiness. |
| `src/ui/map.py`, `src/exports/selection.py` | Render vendored Leaflet and export labelled results with stable licence IDs and matching selection filters. |

## Environmental features and presentation

Layer 72 Lake/River polygons and eligible layer 107 Stream lines are read from the stored PostGIS imports. The build clips accepted geometries to a projected rectangle covering each study region and its 500 m search margin. It retains publisher IDs, feature codes, inventory IDs and coverage status. Distances are calculated in EPSG:3400 from the clipped, unsimplified geometries. The accepted stream codes are `STR-PER`, `CANAL`, `OXBOW-PER` and `DITCH`, matching the provincial comparison. Both water snapshots have quarantined features, so unmatched water results are unknown within 500 m. The four synthetic categories retain their deterministic regional geometry.

The first classroom target uses the five existing categories:

| Demonstration layer | Existing analytical category / label |
|---|---|
| Imported Alberta stream lines and waterbody polygons | `water` — nearest accepted feature across the two layers |
| Invented wetland polygons | `wetland` — synthetic wetland scenario |
| Invented protected-area polygons | `protected_area` — synthetic boundary, not a legal designation |
| Invented critical-habitat polygons | `critical_habitat` — simulated habitat scenario, not an actual species location |
| Invented historical-significance illustration | `esa` — synthetic illustration, not a real 2014 score or legally protected land |

The starter also proposes flood and ecological-occurrence categories. They are optional demo extensions, not prerequisites or automatically authorized real-data ingestion tasks. Ecological occurrences are **not** interchangeable with federal critical habitat. If added, use a scoped category registry and tests throughout validation, analysis, UI, exports and any persisted constraints. Real flood, ACIMS, ABMI/wetlands, crop rasters and province-wide imports remain deferred. Production remains outside scope, including fake production attached to real wells.

Use **Buffer distance** to switch between **50 m**, **100 m**, **250 m** and **500 m**. The imported-water demo opens at 500 m with **Only show wells within the buffer** checked. Each setting includes observed distances at or below the selected radius. Uncheck the box to show all wells matching the other filters. The map, well table and downloads follow the same selection. Choose a well to display its buffer at the selected radius.

The baseline comparison identifies well licences and counts that change at each distance. The map and exports label the imported water results and simulated categories. Licence status comes from the workbook.

Classify from unrounded distances in metres, with inclusive thresholds. A well inside a synthetic polygon has distance zero. Missing synthetic input/coverage is unknown, not a healthy zero or a real-data assurance. Complete coverage means only that the generator supplied the declared synthetic scenario. An absent feature within 500 m does not mean the real well is environmentally safe.

## Launch the classroom mode

From the repository root with the pinned Python 3.12 dependencies installed, launch the local app.

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

The app uses `data/demo/classroom/demo_imported_water.json` by default. For a clean checkout, place the permitted prepared package at that path or set `CLASSROOM_DEMO_PATH` to its location before launch. Install dependencies before going offline and leave the optional OpenStreetMap tiles off.

The Streamlit process needs read access to the package. New JSON and teacher ZIP builds inherit permissions from their output folders on Windows. The app reports a file access error when those permissions prevent it from opening the package.

The revised teacher archive is `outputs/classroom/st37-classroom-imported-water.zip`. Extract it and follow `START.md`. It contains the app, pinned requirements, vendored assets and the prepared package. The earlier synthetic-water archive is `outputs/classroom/st37-classroom.zip`.

Recreate the current package from the original preparation report, its adjacent inventory and the two stored water snapshots. The build uses read-only access to the inventory and PostGIS data.

```powershell
$report = 'data/raw/st37/7b77926624ee1c2c7fb554d8426eab5ac5b1c6a17d7226fce6429cd2b3c1d8f4/report.json'
$evidence = 'AER ST37 release 2026-11-03: exact workbook SHA-256 and all 541,190 coordinate pairs matched the same-release geodatabase. NAD83 projected points match within 0.000109 m. Evidence: docs/st37_excel.md and docs/evidence/st37_datum_2026-11-23.json.'
.\.venv\Scripts\python.exe scripts\prepare_classroom_demo.py --report $report --coordinate-crs EPSG:4269 --crs-evidence $evidence --release-date 2026-11-03 --waterbodies-import-id 9b833be4-ff85-5712-9b8a-7d34be2b761c --streams-import-id 502120a2-a315-56ae-94ac-4d59ebc8963f
.\.venv\Scripts\python.exe scripts\package_classroom_demo.py
```

The package keeps its checksum, source attribution, release date, native and analysis CRS, seed and region definitions. A failed build retains the prior package. Running preparation without water snapshot IDs targets the separate synthetic package. Without coordinate evidence that package contains a reported-coordinate preview.

For the teacher handoff, include the permitted small package, app, dependencies and vendored assets. Keep AER attribution in the release and record the permission basis. See [source and permissions](st37_excel.md) and the [optional real-water workflow](hydrography.md).

## Verification and remaining work

In the **Both** view, Edge verified 0, 1, 5 and 9 visible well markers at 50, 100, 250 and 500 m with imported waterways selected. Turning the buffer filter off showed all 56 wells. The selected well's circle followed the radius, and the 250 m GeoJSON contained the same five wells as the map.

The imported-water package has 33 water features around Red Deer and 36 around Drayton Valley. All 56 well rows and eight synthetic non-water features match the earlier package. The nearest water distances agree with the provincial PostGIS comparisons for all 56 sampled wells. The nine observations within 500 m agree to within 0.000001 m. One of those wells is within 100 m, and the remaining wells without observed matches have unknown results because coverage is incomplete. Edge verified the three region views and the manifest, GeoJSON and map HTML exports with network requests blocked. The extracted teacher app loaded all three region views with an invalid database setting. The full suite passed 153 tests.

On 23 November 2026, Streamlit at `localhost:8501` reported a Windows permission error on the verified JSON. Publishing the same bytes with inherited directory permissions restored access to the JSON and teacher ZIP. The JSON rebuilt byte for byte, and two new teacher archive builds matched each other. Edge and the Streamlit agent API verified 28 Red Deer wells, 28 Drayton Valley wells and 56 in Both. All 153 tests passed in disposable PostGIS.

The retained package reproduced byte-for-byte. All 56 selected records matched the full inventory field by field, and the workbook and inventory hashes matched their recorded values. AppTest and the running Streamlit API verified 28 Red Deer wells and 56 in Both. The projected path was tested on declared-CRS fixtures against the shared 0/50/100/250/500/500.01 m boundaries, geometry interiors, ties and incomplete coverage.

With a disposable PostGIS instance, `python -m pytest -q` passed 146 tests. A separate offline Edge run from an isolated copy used only the app and a small known-CRS test package. It verified two marker clicks, the selected-well buffer and matching CSV, GeoJSON, manifest and standalone HTML.

For the earlier synthetic Water scenario the number of sampled wells within each simulated distance is:

| Region | 50 m | 100 m | 250 m | 500 m |
| --- | ---: | ---: | ---: | ---: |
| Red Deer | 1 | 1 | 2 | 2 |
| Drayton Valley | 1 | 1 | 2 | 3 |
| Both | 2 | 2 | 4 | 5 |

Changing from 500 m to 100 m removes three wells from the simulated shortlist (`0016125`, `0173144`, `0430751`). The shortlist illustrates threshold sensitivity on this sampled scenario. Its counts apply to the generated water shapes. [Phase 7 progress](../DESIGN.md#13-phased-codex-implementation-plan) · [Course milestones](../aida-final-project-tyler-weinkauf/project-progress.md)

The final classroom check launched the extracted teacher ZIP on Windows using installed Python 3.12 dependencies. Microsoft Edge ran with external HTTP requests blocked and requested no remote hosts. The browser verified the three region views, 100 m and 250 m thresholds, two marker clicks and buffers, and matching CSV, GeoJSON, manifest and standalone HTML. The running Streamlit API checked company and category filters. Both regional CSVs matched their rows in the combined export. `python -m pytest -q` passed all 149 tests with a disposable PostgreSQL/PostGIS database. [Checksums and counts](evidence/classroom_2026-11-23.json)

The separate classroom review candidates are `outputs/classroom/AIDA-1145-classroom-candidate.zip` and `outputs/classroom/AIDA-2362-classroom-candidate.zip`. The first contains the analysis-ready table, release lineage and validation. The second contains the map, screenshots and matching tables. Each contains the teacher ZIP. The AIDA 2362 brief specifies QGIS and instructor confirmation of the Streamlit/Folium alternative remains open. [AIDA 1145 evidence](../aida-final-project-tyler-weinkauf/courses/AIDA-1145/EVIDENCE.md) · [AIDA 2362 evidence](../aida-final-project-tyler-weinkauf/courses/AIDA-2362/EVIDENCE.md)
