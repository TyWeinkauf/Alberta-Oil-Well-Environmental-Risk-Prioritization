# Red Deer and Drayton Valley classroom demo

**Status — 20 November 2026.** The offline Streamlit well preview is available from a prepared 27,214-byte package. It has 56 actual ST37 surface-hole records and preserves their source coordinate values. The app's illustrative geometry, distances and exports have a separate documented-CRS path. The retained Excel datum remains open.

Reference archive SHA-256: `cd3bb2b438775ec346d294745651907122789ee85896a95d242c514c75040a53`. The original Word design remains a reference; DESIGN.md remains the maintained project design.

## Agreed direction and interpretation

The next release should demonstrate a small area around **Red Deer and Drayton Valley**, using **actual surface-hole well records already retained from ST37** and **clearly synthetic environmental features**. Keep the existing real-data import tools for optional later use. A classroom presentation must not require an Alberta-wide environmental download or send all 541,190 wells to the browser.

**Course handoff clarification, 20 November 2026.** Use the course briefs already in the repository. The user selected Streamlit/Folium with an optional OpenStreetMap basemap to demonstrate GIS tasks. Show layer toggles, click-to-identify, metre-based buffers, a baseline and changed-threshold comparison, and an accessible map with matching table and exports. Document the projected CRS and how to reproduce the results offline. The preserved AIDA 2362 brief specifies QGIS. The Streamlit approach reflects the user's understanding of acceptable tooling, with instructor confirmation unverified. [AIDA 1145 brief](../aida-final-project-tyler-weinkauf/courses/AIDA-1145/README.md) · [AIDA 2362 brief](../aida-final-project-tyler-weinkauf/courses/AIDA-2362/README.md)

The supplied `oilwell_environment_codex_starter.zip` is a reference, not a replacement project. Its `AGENTS.md`, README, start-here document, source/contract configuration, source-workflow/ST37 notes, synthetic generator, app and analysis SQL were inspected without executing the package. The ZIP's own demo invents both wells and surroundings: its included manifest reports 56 synthetic wells, 22 synthetic features and eight analytical categories. Those are starter-package claims, not newly verified outputs of this repository. Its `oilrisk` commands, database schema and source URLs must not be copied into this project as if already supported/verified.

**Your instruction changes that starter:** the main showcase must retain actual ST37 well IDs, positions and supplied attributes. Only the demonstration environmental features are invented. The starter's requests for fake production rates or eventual Petrinex integration do not override the earlier decision to exclude production.

Required banner and export wording:

> Illustrative classroom demo: real AER ST37 well locations with synthetic environmental features. Distances and proximity bands describe the simulated features only. They do not describe actual environmental conditions, contamination, legal setbacks or the risk of these real wells.

This deliberately labelled illustrative mode is separate from both the existing fully synthetic regression fixture and an all-real screening run. A network/source failure must never silently replace real environmental data with invented features.

## What is already done

| Existing evidence | Implication for the demo |
|---|---|
| Actual ST37 Excel inspected; 541,190 unique licence records, 11 preserved fields, leading zeros retained | Reuse the retained inventory; do not download another well dataset or replace real wells with the starter's invented wells. |
| Full inventory, Drayton Valley candidate CSV, raw checksums, date warnings and provenance retained locally | Prepare small derived regional packages without modifying the full inventory or original workbook. |
| Full ST37 load/repeat tested in a disposable database; six date-warning records reported | Importer behavior is proved. This does not prove the user's permanent database is populated. |
| Streamlit map, stable well selection, licence/company filters, details, exports and metre-based threshold logic tested | Reuse the working components through a small offline dataset adapter. |
| Vendored Leaflet/jQuery assets and no-tile rendering already work | Preserve these; the starter's default online tiles/plugins would not improve offline reliability. |
| Bounded real-water import/preview and raw-property lineage implemented | Preserve as optional real-source functionality. It is not a prerequisite for the synthetic-environment classroom path. |
| Latest retained runtime verification: 142 unit/PostGIS tests plus type/running-app checks | Historical baseline for the current app. New two-region classroom acceptance still needs implementation and fresh verification. |

The app starts in **Classroom demo**. Select **PostGIS workflows** for the existing synthetic database fixture, water preview and verified-source tools.

## Well preservation and proposed regional display

Retain these existing inputs unchanged:

- `aida-final-project-tyler-weinkauf/courses/AIDA-1145/data/ST37_SH.xlsx` — 38,596,313 bytes; SHA-256 `5b7139f06817b3458689bb82a3219c963165e3e671373e493222d948bb08e4f4`.
- `data/raw/st37/7b77926624ee1c2c7fb554d8426eab5ac5b1c6a17d7226fce6429cd2b3c1d8f4/inventory.csv` and its report — all 541,190 records; inventory SHA-256 `acee23f2655e8036aa9bc6d34d45c153328b534602e3f05ed1307d7417c3251e`.
- Existing snapshots, quarantine/warnings, water inventories and any user database records. No DROP, TRUNCATE, in-place replacement or full reload is needed for this demo.

A read-only scan of that inventory on 10 November found:

| Region | Working bounding box `[west, south, east, north]` | Preview candidates | Preview sample |
|---|---|---:|---:|
| Red Deer | `[-113.88, 52.22, -113.74, 52.32]` | 105 | 28 |
| Drayton Valley | `[-115.08, 53.20, -114.94, 53.30]` | 477 | 28 |
| Both | Two separate rectangles, not their combined enclosing rectangle | 582 | 56 |

The Drayton rectangle preserves the existing pilot. The Red Deer rectangle centers the preview on the classroom study area. The preview counts come from the reported decimal-degree coordinates. With CRS evidence, preparation transforms the original coordinates to WGS84 for region membership before projection to EPSG:3400 metres. Final datum-aware counts remain open under 7.1.

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

Use seeded synthetic **lines and polygons**, generated in EPSG:3400 around the retained, unchanged well points. Provide a 500 m environmental margin around each region so edge-well distances remain correct. Use a seed derived from the stable region ID, not its position in a loop: generating Drayton alone must match Drayton generated as part of Both.

The first classroom target uses the five existing categories:

| Demonstration layer | Existing analytical category / label |
|---|---|
| Invented streams, waterbodies and optional seasonal water | `water`, with visible line/polygon/seasonal subtypes; one nearest-water result rather than double-counted scores |
| Invented wetland polygons | `wetland` — synthetic wetland scenario |
| Invented protected-area polygons | `protected_area` — synthetic boundary, not a legal designation |
| Invented critical-habitat polygons | `critical_habitat` — simulated habitat scenario, not an actual species location |
| Invented historical-significance illustration | `esa` — synthetic illustration, not a real 2014 score or legally protected land |

The starter also proposes flood and ecological-occurrence categories. They are optional demo extensions, not prerequisites or automatically authorized real-data ingestion tasks. Ecological occurrences are **not** interchangeable with federal critical habitat. If added, use a scoped category registry and tests throughout validation, analysis, UI, exports and any persisted constraints. Real flood, ACIMS, ABMI/wetlands, crop rasters and province-wide imports remain deferred. Production remains outside scope, including fake production attached to real wells.

Show licence/company filtering, click-to-inspect, 50/100/250/500 m settings, selected-well buffer, category toggles and a compact result table. Show a Baseline vs changed-threshold comparison identifying changed licence IDs/counts. All headings, popups, downloads and screenshots must distinguish actual well attributes from simulated environmental evidence. Use licence status as licence status; it is not verified operational status.

Classify from unrounded distances in metres, with inclusive thresholds. A well inside a synthetic polygon has distance zero. Missing synthetic input/coverage is unknown, not a healthy zero or a real-data assurance. Complete coverage means only that the generator supplied the declared synthetic scenario. An absent feature within 500 m does not mean the real well is environmentally safe.

## Launch the classroom mode

From the repository root with the pinned Python 3.12 dependencies installed, launch the local app.

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

The app uses `data/demo/classroom/demo.json` by default. On this machine the file is prepared locally. For a clean checkout, place the permitted small JSON package at that path or set `CLASSROOM_DEMO_PATH` to its location before launch. Install dependencies before taking the machine offline. Leave the optional OpenStreetMap tiles off for offline maps.

The local archive `outputs/classroom/st37-classroom-preview.zip` contains the app, pinned requirements, vendored assets, the 56-well preview and `START.md`. Its extracted copy launched with the current Windows Python 3.12 environment and showed 28 Red Deer or 56 combined records. The archive is 172,748 bytes with SHA-256 `37659b13a9245ee82fd700f6a85cbc7b4e1214cdd6f533ac1369e32ef3a9b203`.

Recreate the current package from the original preparation report and its adjacent inventory. Both input files are opened read-only.

```powershell
$report = 'data/raw/st37/7b77926624ee1c2c7fb554d8426eab5ac5b1c6a17d7226fce6429cd2b3c1d8f4/report.json'
.\.venv\Scripts\python.exe scripts\prepare_classroom_demo.py --report $report
```

Once the workbook's geographic CRS has been verified, supply both `--coordinate-crs` and `--crs-evidence` to the same preparation command. The resulting package activates the synthetic layer controls, buffers, threshold comparison, GeoJSON and standalone map. The package keeps its checksum, source attribution, native and analysis CRS, seed and region definitions. A failed build retains the prior package.

For the teacher handoff, include the permitted small package, app, dependencies and vendored assets. Keep AER attribution in the release and record the permission basis. See [source and permissions](st37_excel.md) and the [optional real-water workflow](hydrography.md).

## Verification and remaining work

The retained package reproduced byte-for-byte. All 56 selected records matched the full inventory field by field, and the workbook and inventory hashes matched their recorded values. AppTest and the running Streamlit API verified 28 Red Deer wells and 56 in Both. The projected path was tested on declared-CRS fixtures against the shared 0/50/100/250/500/500.01 m boundaries, geometry interiors, ties and incomplete coverage.

With a disposable PostGIS instance, `python -m pytest -q` passed 146 tests. A separate offline Edge run from an isolated copy used only the app and a small known-CRS test package. It verified two marker clicks, the selected-well buffer and matching CSV, GeoJSON, manifest and standalone HTML.

Final classroom acceptance requires the actual workbook datum, a projected regional package, screenshots and a sensitivity result from that package, and separate course handoffs. [Phase 7 progress](../DESIGN.md#13-phased-codex-implementation-plan) · [Course milestones](../aida-final-project-tyler-weinkauf/project-progress.md)
