# Red Deer and Drayton Valley classroom demo

Scope review and implementation handoff, **10 November 2026**. The review/documentation is complete; the new classroom mode is **not implemented yet**. This document explains how to adapt the existing project while preserving its data and tested functionality.

Reference archive SHA-256: `cd3bb2b438775ec346d294745651907122789ee85896a95d242c514c75040a53`. The original Word design remains a reference; DESIGN.md remains the maintained project design.

## Agreed direction and interpretation

The next release should demonstrate a small area around **Red Deer and Drayton Valley**, using **actual surface-hole well records already retained from ST37** and **clearly synthetic environmental features**. Keep the existing real-data import tools for optional later use. A classroom presentation must not require an Alberta-wide environmental download or send all 541,190 wells to the browser.

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

The current `app.py` requires `DATABASE_URL` before displaying its controls, and its existing demo uses PostGIS with two accepted synthetic wells. It is **not yet** the proposed credential-free regional classroom demo. The local `.env` still contains placeholders. No user database was connected to or changed in this scope review.

## Well preservation and proposed regional display

Retain these existing inputs unchanged:

- `aida-final-project-tyler-weinkauf/courses/AIDA-1145/data/ST37_SH.xlsx` — 38,596,313 bytes; SHA-256 `5b7139f06817b3458689bb82a3219c963165e3e671373e493222d948bb08e4f4`.
- `data/raw/st37/7b77926624ee1c2c7fb554d8426eab5ac5b1c6a17d7226fce6429cd2b3c1d8f4/inventory.csv` and its report — all 541,190 records; inventory SHA-256 `acee23f2655e8036aa9bc6d34d45c153328b534602e3f05ed1307d7417c3251e`.
- Existing snapshots, quarantine/warnings, water inventories and any user database records. No DROP, TRUNCATE, in-place replacement or full reload is needed for this demo.

A read-only scan of that inventory on 10 November found:

| Region | Working bounding box `[west, south, east, north]` | Candidate records | Proposed initial display |
|---|---|---:|---:|
| Red Deer | `[-113.88, 52.22, -113.74, 52.32]` | 105 | 28 |
| Drayton Valley | `[-115.08, 53.20, -114.94, 53.30]` | 477 | 28 |
| Both | Two separate rectangles, not their combined enclosing rectangle | 582 | 56 |

The Drayton rectangle preserves the existing pilot. The Red Deer rectangle is a proposed small window around the starter's approximate map centre. Counts use the raw latitude/longitude envelope, have distinct licences within each region and contain zero of the retained date-warning rows. **They are feasibility counts, not datum-verified geographic extracts or an already implemented display.** Confirm the Excel coordinate datum before projecting actual well points; this remains open in design step 5.4b. EPSG:3400 must not be assigned directly to degree coordinates.

The initial 28-per-region limit is a proposed performance/presentation setting, not a source-data deletion or claim of representativeness. Use deterministic hash/seed selection by original licence ID, record the selection method and selected IDs in the manifest, and choose wells independently of the synthetic outcomes. Do not take the first 56 workbook rows or prioritize apparently favourable proximity results. Offer Red Deer / Drayton Valley / Both controls and display candidate count separately from displayed count. An optional larger regional view can use clustering/viewport limits; it must never fall back to all-Alberta rows.

When a verified inventory already exists in PostGIS, read its selected snapshot with parameterized regional queries. Otherwise read the retained CSV once to prepare the small package. Reading/filtering an existing inventory is not a new province-wide database import. The teacher's runtime should read only the prepared regional files, not the original Excel or full CSV.

## Reuse the project rather than merge the starter wholesale

| Current component / mismatch | Adjustment still required |
|---|---|
| `src/sources/st37.py`, `src/db/st37.py` already preserve this workbook's actual schema | Add regional export from the existing inventory/snapshot. Preserve licence ID, actual coordinates, licensee, legal location and licence-status meaning. Leave UWI/operator/production unavailable when absent. |
| `config/study_area.live.yml` defines only Drayton Valley | Add a separate demo-region configuration for both rectangles, seed and display limit. Preserve the real-source configuration. |
| `app.py` opens PostGIS before mode selection | Add an explicit illustrative-mode branch before database/real-source preflight, backed by small local files. Keep the existing DB workflow behind its own mode. |
| Current metadata/UI distinguish only `demo` and `live` | Add an explicit illustrative dataset identity and entity-level real/synthetic provenance. Do not label the actual wells as fully synthetic or the calculated results as all-real. Reset incompatible selections on mode/region changes. |
| `src/ui/map.py`, filters and exports already work | Feed them a compatible local dataset contract, retaining stable record keys and the real textual licence ID. Never jitter actual well positions or attach invented companies/statuses/production. |
| `src/spatial/engine.py` calculates through PostGIS | Add an offline GeoPandas/Shapely path with the same units, boundary rules, tie handling and coverage semantics. Reuse pure classification helpers and test parity on small fixtures. |
| Five category contracts/SQL constraints and some fixed `well_count * 5` checks exist | Keep the first classroom release within supported categories. Generalize the registry/accounting before adding new category codes; editing only a legend is insufficient. |

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

## Remaining implementation — ordered handoff

All rows below are **Not started**; the current change documents and checks feasibility only.

| Step | Deliverable / planned files | Completion proof |
|---|---|---|
| 7.1 | Confirm geographic datum, record two region definitions and configurable display limit/seed; planned `config/demo_regions.yml` | Verified source CRS evidence; datum-aware boundary checks; no full-data changes. Offline UI/generator work can proceed independently while datum confirmation is pending. |
| 7.2 | Regional well-package exporter reading retained inventory or selected DB snapshot; planned `scripts/prepare_classroom_demo.py` and `src/demo/regions.py` | Original and full-inventory hashes unchanged; unique real IDs/attributes match source; region-before-sampling logic; deterministic same selected IDs on repeat; no province-wide import. |
| 7.3 | Seeded synthetic environmental generator and manifests; planned `src/demo/features.py` | Five supported categories in each region; valid EPSG:3400 geometry and 500 m margin; stable independent per-region seeds; every environmental record explicitly synthetic. |
| 7.4 | Small-file dataset adapter and offline distance analysis; planned `src/demo/data.py`, `src/demo/spatial.py` | Geometric distances/classification agree with shared reference fixtures, including 0/50/100/250/500/500.01 m, interiors, ties, missing coverage and complete row accounting. |
| 7.5 | App mode and region selector before DB connection, persistent well details, provenance/buffers/exports | Starts with no DATABASE_URL and no DB service; default shows at most the configured regional sample; actual-well/synthetic-environment labels persist everywhere; live workflows remain isolated and opt-in. |
| 7.6 | Teacher launch/setup notes and portable small permitted package; new unit/UI/clean-run tests | Run with network blocked, no PostgreSQL and no full source file; map vectors/assets, mode/region/filters, selected wells and exports work; repeat/failed-generation retention and unchanged source hashes verified. Record package sizes and actual commands once implemented. |
| 7.7 (optional) | Synthetic flood/ecology extensions after category-registry audit | No fixed-five-category assumptions; occurrence vs critical-habitat distinction; synthetic-only provenance; no new live downloads. Not required for initial classroom release. |

Keep generated classroom files under an ignored path such as `data/demo/classroom/<identity>/`, separate from original inventories and official outputs. Publish a new package atomically and retain the previous successful package on failure. The manifest should record well-source hash/snapshot, coordinate CRS/evidence, region bounds, sampling seed/method/counts, generator version/seed, synthetic categories, output hashes, classification settings and disclaimer. Export only the small permitted regional well subset for presentation; check attribution/redistribution requirements before packaging real records. Do not ship passwords, database dumps, full inventories or publisher originals.

Dependencies must be installed before a fully offline classroom run; supply tested setup instructions or an appropriate offline dependency preparation route. OSM tiles are optional online decoration. Use the existing no-tile/vendored-assets path when offline and do not bundle downloaded map tiles.

## What can be run now versus what cannot

Existing ST37 preparation/import commands and the optional real-water workflow are documented in [st37_excel.md](st37_excel.md) and [hydrography.md](hydrography.md). The current Streamlit app and synthetic demo still need a configured PostGIS database. No `oilrisk` package or starter CLI was installed into this repository, and the new `prepare_classroom_demo.py` command does not exist yet. Do not present these planned commands as ready to run.

The latest runtime proof remains the previous 142-test integration verification. This review did not execute the starter or rerun application tests because no application code changed. It verified source/inventory checksums, scanned the retained CSV for the two proposed region counts, inspected implementation gaps, and checked the documentation. Full-Alberta environmental ingestion and resolution of the real-water quarantine are optional-real-mode work, not blockers for synthetic classroom environmental features.

The maintained [DESIGN.md](../DESIGN.md) tracks D.3 as the review and Phase 7 as pending implementation. [Course progress](../aida-final-project-tyler-weinkauf/project-progress.md) must continue distinguishing implementation, demonstrated classroom behavior and actual course feedback/submission.
