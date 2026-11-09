# Alberta Oil Well Environmental Screening

Codex implementation design • AIDA 1145 Data Engineering + AIDA 2362 GIS • Version 1.0 • 8 November 2026

Objective: A reproducible, locally hosted Streamlit web application that retrieves permitted Alberta well/environmental data, validates and loads it into PostgreSQL/PostGIS, computes proximity at 50/100/250/500 metres, and displays clickable wells with company, legal land location and available AER well attributes on an OpenStreetMap basemap.

> Working design and implementation tracker. Converted from [the original Word design](<Alberta_Oil_Well_Streamlit_Codex_Design (1).docx>); the original is retained. The numbered design sections below preserve its scope.

## Progress tracking

Update this document whenever work on a scoped step starts or finishes. Set the step to **In progress** before starting it and to **Complete** only after its completion proof has been verified. Use **Not started** for untouched work. Record the date, evidence, and any remaining work or blocker in section 13. Keep completed substeps visible while their parent phase remains in progress. Reopen a completed step if later checks show its completion proof no longer holds.

Section 13 tracks implementation work; section 12 tracks acceptance checks; section 16 tracks unresolved decisions. Check acceptance and decision items only when their evidence is available, and record that evidence with the related step in section 13. The pipeline states in section 5 describe application runtime behavior, not project progress. Course milestone tracking remains in [project-progress.md](aida-final-project-tyler-weinkauf/project-progress.md).

**Current status — 2026-11-08:** Current scope is AER well locations/attributes plus water, protected areas and critical habitat; Petrinex is excluded. Regional preparation now reads original local GIS/ZIP/FileGDB inputs directly and creates small immutable study-area packages with parent checksums and scope enforcement. Ordinary import caps remain unchanged. All 128 tests pass, including prepared-package PostGIS distances and failed wider-scope retention. Actual ST37 schema/terms, surface-key uniqueness, large-original performance and a bounded official-data run remain open. Phase 6 candidate/handoff work is retained; no official analytical dataset has been loaded.

## 1. Scope, success criteria and guardrails

- Primary user: environmental reclamation screening analyst. The output identifies wells for further investigation, not verified environmental hazards.
- One-click “Run pipeline” from Streamlit; progress, stage statuses, failures and audit summary visible. Cached reruns; production is outside the current scope.
- Selectable Alberta study area (start with small configured bounding box or region), company filter, environmental-layer filter and four proximity thresholds.
- Click a well marker to see ID, licensee, reported operator/producer where supported, LSD/legal location if present, well status, closest environmental feature by category, with missing attributes explicitly unavailable.
- Export CSV/GeoJSON results, map screenshot or HTML where feasible, validation report, provenance manifest, and run metadata.
- No QGIS dependency. GIS calculations in PostGIS/GeoPandas; OpenStreetMap is the basemap only.
- Use a clear training-only disclaimer; do not present proximity as contamination likelihood or engineering advice.

## 2. Evidence and source decisions

**Confirmed intended data scope (2026-11-08):** The completed project will use real AER ST37 wells, Alberta surface water, Alberta parks/protected areas and federal critical habitat, with OpenStreetMap as the basemap. Optional wetlands and historical 2014 ESA remain subject to the source conditions below. The supplied [Dataset and CRS Reference](docs/dataset_reference.md) is now transcribed into the repository and its source metadata recorded in `config/source_catalog.yml`. Synthetic fixtures are development/test evidence only. Live acquisition remains Phase 4; the supplied document does not include actual endpoints or layer IDs.

**Scope revision (2026-11-08):** The user chose to skip Petrinex. Monthly production, facility allocation and production joins are excluded from current acceptance. AER ST37 supplies well/geometry/licence attributes; its production-string metadata is not monthly volume history. Phase 5 is now AER well-attribute/detail integration. Previously completed production code/tests/migrations remain as legacy functionality, but no Petrinex configuration/download is required and the default UI hides it. See [ST37 guide review](docs/st37_reference.md) and [download checklist](docs/download_inputs.md).

**Runtime access clarification (2026-11-08):** The user may access sources through publisher APIs, direct CSV/GeoJSON downloads or files downloaded separately when running the program. ChatGPT/Codex cloud-access failures are environment-specific observations, not evidence that a dataset is unavailable everywhere. Keep the intended real sources; verify schemas/terms against actual responses or supplied files in the execution environment. Remote HTTP/ArcGIS and configured user-downloaded local-file ingestion are implemented; actual source-specific verification remains open. See [data access routes](docs/data_access.md).

User-provided dataset reference identifies AER ST37 well data, Alberta Base Water Feature, parks/protected areas, federal critical habitat, optional wetlands and 2014 ESA, and OpenStreetMap. Confirm current source URLs, format, schemas, CRS, permissions and timestamps before implementation. Earlier planning described AER shapefiles; source format must be verified at runtime and should support file geodatabase ZIP as well as shapefile where available.

| Source | Purpose / acquisition | Cautions |
| --- | --- | --- |
| AER spatial wells / ST37 successor | Official downloadable spatial dataset; ingest file geodatabase using pyogrio/GDAL if current format requires it | Potentially very large; verify field mapping, CRS, licensee, update date, terms |
| Alberta Base Water Feature | ArcGIS REST selected rivers, streams, lakes / reservoirs | Query service metadata and pagination; layer IDs configurable |
| Alberta parks and protected areas | ArcGIS FeatureServer geometries | Boundary is screening geometry, not legal determination |
| Federal critical habitat | Federal download/service; filter to Alberta | EPSG:3978 in reference; sensitivity/generalization caveats |
| Wetlands / ESA | Optional after licensing/coverage check | Older inventories; ESA 2014 comparison only |
| Petrinex conventional volumetrics | Removed from current scope | Legacy code retained; no production requirement or download |
| OpenStreetMap | Tile basemap with attribution | Not used for measuring distance; obey tile usage limits |

Source reference document lists EPSG:3400 for provincial GIS layers and EPSG:3978 for federal critical habitat; inspect actual downloaded metadata and AER .prj/CRS rather than assume. Keep URLs and layer IDs in config/source_catalog.yml, not hard-coded into application logic.

## 3. System architecture

Streamlit UI → orchestrator → source adapters (AER file / ArcGIS REST / federal data) → immutable raw cache → data contracts and quarantine → normalized staging → PostGIS authoritative tables → spatial analysis SQL → materialized results / cached query → Folium + streamlit-folium OpenStreetMap UI → CSV/GeoJSON/JSON evidence exports.

Use Python 3.12 or 3.13 as supported by dependencies, PostgreSQL 17 + PostGIS, SQLAlchemy, psycopg, GeoPandas, pyogrio, shapely, requests/httpx, pandas, pandera or pydantic, pytest, Streamlit, folium, streamlit-folium, and optionally Alembic. Pin working versions after validation. Keep download and transformation outside Streamlit rerun side effects.

## 4. Proposed repository structure

Preserve existing README.md, project-charter.md, scope-matrix.md, project-progress.md, shared-resources/, courses/AIDA-1145/, courses/AIDA-2362/, and presentation/. Add:

- app.py; pages/01_Map.py, 02_Data_Quality.py, 03_Run_History.py
- src/config.py, src/orchestrator.py, src/contracts/, src/sources/, src/transform/, src/db/, src/spatial/, src/production/, src/ui/, src/exports/
- config/source_catalog.yml, config/study_area.yml, .env.example, requirements.txt or pyproject.toml
- sql/migrations/, tests/unit/, tests/integration/, tests/fixtures/, scripts/setup_db.py, scripts/demo_seed.py
- data/raw/, data/cache/, data/quarantine/, outputs/runs/ (all generated/large content ignored by Git)
- docs/architecture.md, docs/data_dictionary.md, docs/reproducibility.md, docs/limitations.md

## 5. Workflow: run button and state machine

1. Preflight: test DB connectivity, PostGIS extension, disk space, configured sources, write permissions and selected study area.
2. Acquire: download or reuse checksum-verified raw source snapshots; record URL, access timestamp, original filename, source version, ETag/Last-Modified if supplied.
3. Inspect: detect file type, layer, field names, CRS, row counts, extent and API pagination; fail closed on missing CRS.
4. Contract validation: validate required IDs, geometry, allowed ranges, geometry types, date/number formats and duplicates. Save rejected records with reason codes.
5. Transform: standardize column names, normalize identifiers/company names, repair only safe geometries, clip environmental features to study area plus 500 m margin, transform to EPSG:3400.
6. Load: transactional staging/upsert into PostGIS; preserve raw snapshot and run ID. Avoid deleting last successful dataset if a new run fails.
7. Well attributes: retain AER surface-location grain, licence identifier, licensee, legal location and licence-status meaning; show unavailable optional fields without inventing a UWI/operator.
8. Analyze: ST_DWithin and ST_Distance to actual feature geometries, compute minimum distance by category, assign inclusive threshold bands, store results and QA metrics.
9. Publish: mark run succeeded atomically, refresh map data and expose run reports and exports.

States: idle → preflight → downloading → validating → transforming → loading → analyzing → succeeded / failed / cancelled. Prevent duplicate simultaneous runs using a database advisory lock or equivalent; log errors without leaking secrets. A failed refresh leaves the previous successful results readable.

## 6. Data contracts and quality checks

| Entity | Required contract | Quarantine / response |
| --- | --- | --- |
| Wells | source_well_id unique within source; valid point geometry; coordinate bounds; source provenance | Null/duplicate ID, invalid location or unknown CRS rejected; missing optional LSD/status retained as null |
| Environmental features | source_feature_id or stable derived hash; category; valid line/polygon geometry; CRS | Invalid/empty geometry quarantined; record repair before/after and reason |
| Companies | source name retained; normalized search label; company type (licensee/operator) | Do not merge distinct companies based only on fuzzy text |
| Legacy production (outside scope) | Retained contracts/migrations only; not a current required input | Default app hides this workflow |
| Run manifest | run ID, source versions, counts, rejects, CRS, elapsed time, analysis configuration | Any source failure recorded; partial run not published |

Tests include missing required column, malformed coordinates, duplicate well identifier, invalid polygon, unknown CRS, pagination error, HTTP retry, idempotent rerun, out-of-study-area feature and nullable AER attributes. Legacy production join tests are retained separately. Report accepted/quarantined counts and examples without silently dropping records.

## 7. PostGIS database design

| Table | Important fields |
| --- | --- |
| pipeline_runs | run_id PK, started_at, finished_at, status, study_area, config_hash, error_summary |
| source_snapshots | snapshot_id PK, run_id FK, source_key, url, retrieved_at, checksum, license_note, native_crs, record_count |
| wells | well_pk PK, source_well_id, uwi_if_available, licensee_name, operator_name_if_verified, lsd_text, status, geom geometry(Point,3400), snapshot_id |
| environmental_features | feature_pk, source_key, feature_type, source_feature_id, name, geom geometry(Geometry,3400), snapshot_id |
| production_monthly | production_pk, source_record_id, reporting_facility_id, well_identifier_nullable, period, product, activity, volume, unit, attribution_level, snapshot_id |
| production_well_links | well_pk, production_pk, join_method, evidence, confidence_status; only verified links used in well chart |
| well_proximity | run_id, well_pk, category, nearest_feature_pk, distance_m, within_50, within_100, within_250, within_500 |
| quarantine_records | run_id, source_key, record_reference, reason_code, reason_detail, raw_payload_reference |

The production tables above are retained migration history outside the current scope; no data/table deletion is part of this scope change.

Indexes: GIST on well and environmental geometries; B-tree on source_well_id, normalized company name, production period, run_id, and proximity (run_id, well_pk, category). Use migration scripts; apply primary/foreign key constraints. Store geometry in EPSG:3400, convert to EPSG:4326 for Leaflet/Folium rendering.

## 8. Spatial algorithm and classification

Distances are in metres using EPSG:3400. ST_Distance(point, polygon) returns 0 for wells inside a polygon; distance to lines is to the line geometry. Use ST_DWithin(point, feature, 500) to preselect candidates, then ST_Distance and ROW_NUMBER to find nearest feature per well and category. For performance, query only study-area geometries with a 500 m margin; distinguish no feature within 500 m from unavailable or incomplete source coverage.

| Band | Interpretation | Display suggestion |
| --- | --- | --- |
| 0–50 m | At or within 50 m of selected feature | Red |
| >50–100 m | Beyond 50 m and at or within 100 m | Orange |
| >100–250 m | Beyond 100 m and at or within 250 m | Yellow |
| >250–500 m | Beyond 250 m and at or within 500 m | Blue |
| >500 m / none nearby | No selected feature within 500 m | Gray |

Bands are mutually exclusive for display, but boolean within_X flags are cumulative. A well can match multiple categories; overall band uses the minimum eligible distance across selected categories. Recompute the overall band when category filters change. Label results “proximity screening” rather than numerical environmental risk scores.

## 9. Streamlit interface and clickable wells

### Sidebar

- Study region selector, producer/licensee searchable multiselect, well status, environmental category checkboxes, distance threshold selector (50/100/250/500 m), available AER attribute filters.
- Buttons: Run full pipeline, Use demo dataset, Clear filters, Export current selection. Disable expensive actions while a run is active.

### Main screen

- Top: source freshness, last successful run, well count, matched counts by threshold, quarantined count, current filter summary.
- Middle: Folium OpenStreetMap map with clustered or canvas-rendered well markers, legend, optional environmental overlays and threshold buffers. Start with a manageable study area; use viewport-based queries and marker clustering for performance.
- Well click: marker popup contains well ID and concise company/status plus “View details”; use streamlit-folium last_object_clicked / last_object_clicked_popup or a stable marker ID in the returned interaction to update st.session_state.selected_well_id. Never rely on marker coordinates as the primary key.
- Right-side detail panel or below-map panel persists after rerenders: official well ID/UWI if present, licensee, verified operator/producer, LSD/legal description, well status, latitude/longitude, source snapshot and update date, nearest feature by category, distances and threshold flags.
- Well detail panel: surface-site identifier, licensee, legal location, licence status, coordinates, source provenance and nearest environmental results. No monthly-production section appears with the current catalogue.
- Clicking another well replaces detail panel; changing buffer or producer filters retains selection if well remains in current result, otherwise show “Selected well is outside current filters” with option to clear selection.

Do not assume production data, LSD, UWI or operator is always present. Show “Not available from this source” rather than blank or invented values. Distinguish licensee, operator and producer labels in the UI.

## 10. AER well attributes and detail integration

Use the surface-hole layer as the proposed site-screening location grain, subject to actual-file validation. The supplied guide lists `Well_Licence_Number`, `Licensee`, `Licence_Status`, `Licence_Surface_Location_Label` and surface coordinate columns. Verify actual geometry/CRS, field types and identifier uniqueness, and preserve the distinction between licence status and operational well status. The listed surface layer has no UWI; leave it unavailable unless separately supported. Petrinex and monthly production are removed from this scope. Existing optional production code/migrations are retained without requiring their completion or a download.

## 11. Installation and reproducibility

1. Clone GitHub repository; install supported Python and PostgreSQL 17/PostGIS (or documented Docker Compose option).
2. Create virtual environment and install pinned dependencies; copy .env.example to .env and enter local DB connection details. Never commit .env.
3. Run python scripts/setup_db.py (creates schema and extensions with appropriate permissions) and streamlit run app.py.
4. Click “Use demo dataset” to validate the complete workflow offline with small synthetic fixtures; click “Run full pipeline” only when live data and disk space are available.
5. Export run manifest and results. Another user should be able to repeat the same fixture results and compare hashes / row counts.

For live source runs, clearly document network requirement, source rate limits, download sizes and that exact results may change with source updates. Include cached sample fixtures in Git only if redistribution is permitted; synthetic demo fixtures are safest.

## 12. Testing and acceptance criteria

- [ ] A clean clone can start the app with documented steps and complete the synthetic demonstration without access to live data.
- [x] A run produces raw snapshot metadata, contract validation metrics, quarantine records, PostGIS tables and an exportable manifest.
- [x] A second run with unchanged snapshots does not duplicate wells or proximity rows. Legacy production repeat checks remain historical evidence.
- [x] Distances are verified against known synthetic examples at 0, 50, 100, 250, 500 and just-over-500 metres; ensure inclusive boundaries and correct category filtering.
- [x] Clicking a map well opens the correct persistent detail panel and shows company, LSD if present, distances, and available AER attributes without requiring production.
- [x] Changing producer filter, threshold and category changes counts and map markers consistently; exporting matches the filtered table.
- [ ] Failed downloads, missing CRS, missing AER fields and invalid geometries show informative status and do not corrupt last successful results.
- [ ] The README and each course package separately identify methods, evidence, limitations and submission deliverables.

Phase 1–3 evidence: fixture metadata/validation, known distances, stable marker/details and filtered export parity are verified. The available company filter is explicitly licensee-based; no producer attribution or production chart is fabricated. A real Chromium test proves offline map interaction and standalone HTML. Clean test-database UI initialization is verified; a released fresh-clone handoff remains open for Phase 6. The unchanged-input rerun criterion is now verified by local-file integration and isolated-checkout repeated CLI counts. Phase 6 candidate checks also verify fresh dependency installation and both offline browser smokes; exact final committed-checkout/platform acceptance, live-source failure presentation and final course packages remain open.

## 13. Phased Codex implementation plan

| Phase | Codex task | Completion proof | Status | Last updated | Evidence / remaining work |
| --- | --- | --- | --- | --- | --- |
| 0 | Audit existing repo and preserve course structure; create config and architecture files | File tree, no deleted course artifacts | Complete | 2026-11-08 | Configuration and architecture files added; original course structure retained; see steps 0.1–0.3. |
| 1 | Local DB setup, migrations, synthetic fixtures and contracts | pytest green; demo rows in PostGIS | Complete | 2026-11-08 | 32 tests passed (25 unit, 7 PostGIS integration); setup and seed commands verified in a clean venv; demo counts 2 wells/2 features/6 quarantined, unchanged on rerun. See docs/reproducibility.md. |
| 2 | Spatial proximity engine and tests | Known distance fixtures pass | Complete | 2026-11-08 | Known-distance and selection tests passed; synthetic water demo distances 50/150 m; 500-to-50 m threshold changes matches 2 to 1. See docs/spatial_methodology.md. |
| 3 | Streamlit map, filters, click-to-detail and export | Interactive demo with stable selection | Complete | 2026-11-08 | Offline interactive demo and stable selection verified by Chromium; 67 Python tests passed. Published OSM tile access subsequently returned HTTP 200; see docs/ui_workflow.md. |
| 4 | Real AER and provincial/federal adapters, caching and provenance | Small region live ingestion with manifest | In progress | 2026-11-08 | Acquisition framework and simulated-source tests pass; discovery now reaches catalogue/public pages, but actual service/download access, schemas and real pilot remain incomplete. See docs/source_verification.md. |
| 5 | AER well attributes and detail integration | Actual well/licence/location attributes render with correct meaning and unavailable fields | In progress | 2026-11-08 | Replaces the removed Petrinex milestone. Guide reviewed; actual surface-layer fields, IDs and UI mapping remain to be verified. See docs/st37_reference.md. |
| 6 | Performance, run recovery, documentation and course evidence | Fresh-clone demo and separate deliverable folders | In progress | 2026-11-08 | Starting concurrency/recovery checks, bounded performance evidence, fresh-checkout demo and handoff documentation. Real-data evidence remains dependent on Phases 4–5. |

### Implementation steps

Update individual steps as work progresses; split a step into smaller rows when needed. A phase is complete only when all its required steps and the phase completion proof are verified. Legacy production steps 5.1–5.3 are retained as history outside the revised Phase 5 acceptance; Out of scope denotes user-removed work, not completed verification.

| Step | Scope | Status | Last updated | Evidence / remaining work |
|---|---|---|---|---|
| D.1 | Convert design to Markdown and establish ongoing tracking | Complete | 2026-11-08 | This document preserves all 16 design sections and tables; tracking instructions are in AGENTS.md. |
| D.2 | Clarify runtime/API/download access independently of cloud discovery limits | Complete | 2026-11-08 | User clarification recorded; src/sources/files.py, pipeline.py and scripts/inspect_production.py inspected. docs/data_access.md distinguishes current remote acquisition/local inspection from full local import tracked separately in 4.2c. |
| 0.1 | Inspect repository and retain course structure | Complete | 2026-11-08 | Existing README, charter, scope matrix, progress record, both course briefs and design inspected; course structure retained. |
| 0.2 | Create application and source/study-area configuration | Complete | 2026-11-08 | config/source_catalog.yml, config/study_area.yml and src/config.py added; strict config tests pass; unverified live sources remain disabled. |
| 0.3 | Create architecture documentation | Complete | 2026-11-08 | docs/architecture.md documents implemented boundaries, transaction/retry behavior and planned components; original course artifacts retained. |
| 1.1 | Prepare cloud Python dependencies and local PostgreSQL/PostGIS | Complete | 2026-11-08 | Onboarding: Python 3.12, pinned dependencies, PostgreSQL 17/PostGIS; 6 synthetic stack checks passed, Streamlit HTTP check passed, DB restart and setup repeatability passed. Reusable install/start instructions saved and environment published. Helpers/results retained outside checkout under /workspace/alberta-environment; these are environment checks, not application tests. |
| 1.2 | Add database migrations and setup script | Complete | 2026-11-08 | sql/migrations/001_initial.sql and scripts/setup_db.py; migrations applied to PostgreSQL 17/PostGIS and repeated safely; checksum and DB constraint tests passed. |
| 1.3 | Add synthetic fixtures and demo seed | Complete | 2026-11-08 | tests/fixtures/demo.json and scripts/demo_seed.py; two runs produced the same run ID with 2 wells, 2 features and 6 quarantined records; reports written. |
| 1.4 | Implement contracts, validation and quarantine behavior | Complete | 2026-11-08 | src/contracts/spatial.py; CRS, extent, geometry, optional fields and duplicate-ID checks passed; failed-load rollback and raw-cache checks passed. |
| 1.5 | Document setup and verify Phase 1 integration tests | Complete | 2026-11-08 | README.md has Windows/cloud setup and .env.example; docs/reproducibility.md records clean-venv checks and 32 passing tests. Windows instructions supplied but not executed on Windows. |
| 2.1 | Implement spatial proximity calculation and classification | Complete | 2026-11-08 | src/spatial/engine.py, src/spatial/classification.py and migration 002 implement actual-geometry distances, stable nearest ties, explicit coverage states and cumulative flags. scripts/analyze_demo.py writes analysis/sensitivity JSON. |
| 2.2 | Test known distances, inclusive boundaries and category changes | Complete | 2026-11-08 | 61 tests passed overall; exact 0/50/100/250/500/500.01 m fixtures, polygon interiors, line geometry, category/threshold sensitivity, run isolation, reruns, coverage downgrade and transactional rollback verified. |
| 2.3 | Record supplied reference and clarify intended real-data sources | Complete | 2026-11-08 | docs/dataset_reference.md transcribes the supplied document; config/source_catalog.yml includes core real sources, optional wetlands/ESA, basemap-only OSM and CRS/licensing reference notes. Endpoints/permissions remain unverified until acquisition. |
| 3.1 | Build Streamlit workflow controls, status and map | Complete | 2026-11-08 | app.py and src/orchestrator.py provide explicit demo action/stages, read-only dashboard reruns, map, quality and session history. Empty test DB initialized through AppTest; offline browser startup/action passed. |
| 3.2 | Implement filters, stable click selection and well details | Complete | 2026-11-08 | Actual Chromium marker clicks select the correct stable-ID detail panel; threshold/company filters preserve selection, show outside-filter status and update markers/counts. 67 Python checks passed; production is explicitly unavailable. |
| 3.3 | Implement exports matching the filtered results | Complete | 2026-11-08 | CSV/GeoJSON/manifest downloads agree with filtered IDs, distances and counts; downloaded standalone HTML renders one marker for one filtered well offline. Vendored asset hashes and popup escaping checked. |
| 4.1 | Verify live sources, schemas, CRS, permissions and study area | In progress | 2026-11-08 | Drayton Valley pilot defined. Published discovery access works; parks catalogue and Petrinex documentation inspected. New service/download hosts are CONNECT-denied; AER returns HTTP 403 and Canada search HTTP 429. See docs/source_discovery.md. |
| 4.2 | Implement AER and provincial/federal source adapters | In progress | 2026-11-08 | Generic ZIP file/ArcGIS adapters are implemented/tested. Source-specific official URLs, layers and mappings cannot be finalized until publisher metadata is accessible. |
| 4.3 | Add snapshot caching, checksums, provenance and small-region live validation | In progress | 2026-11-08 | Immutable HTTP/source bundles, provenance, atomic DB publication and failure retention are tested with simulated sources. An actual official-data regional run remains blocked/unrun. |
| 4.1a | Recheck published access and discover provincial/Petrinex resource hosts | Complete | 2026-11-08 | Fresh HTTP requests, official parks catalogue, Petrinex public pages/terms and two learning aids inspected; URLs/statuses/hashes and remaining destination failures in docs/source_discovery.md and docs/evidence/source_discovery_2026-11-08.json. Full source/schema verification is still open. |
| 4.1b | Review supplied ST37 guide and document manual-download/provenance workflow | Complete | 2026-11-08 | All four guide pages reviewed; surface/bottom/string fields, archive limits and self-download workflow in docs/st37_reference.md and download_inputs.md. Fresh environmental metadata/resources and SHA evidence retained. git check-ignore confirms all data/ excluded and no tracked data files; actual file inspection still open. |
| 4.1c | Consolidate publisher links and explicit environmental download formats | Complete | 2026-11-08 | docs/download_inputs.md now lists publisher/metadata/REST links, the listed habitat FileGDB ZIP, conditional water/parks vector export choices and unsupported KML/WMS/PDF/XLSX distinctions. Fresh catalogue API metadata checked; receipt in docs/evidence/download_checklist_2026-11-08.json. Actual files/layers remain unverified. |
| 4.2a | Implement generic bounded file and ArcGIS acquisition adapters | Complete | 2026-11-08 | Tests read real GIS file formats from synthetic HTTP servers, inspect CRS/fields, verify ArcGIS ID paging and reject partial pages; official schema compatibility is not claimed. |
| 4.2b | Verify and configure each official source-specific endpoint/mapping | In progress | 2026-11-08 | Official parks service URL/licence metadata recorded; actual layers/fields/CRS remain uninspected behind new service-host restrictions. Catalogue stays disabled/unverified. |
| 4.2c | Add user-downloaded local GIS/CSV inputs with provenance and shared validation | Complete | 2026-11-08 | src/sources/local.py, coordinate CSV reader, CLI/app catalogue selection and disabled template implemented. 113 tests pass, including offline four-source local-file load, 50 m distance, string IDs, quarantine, repeat identity and failed-import retention. Official compatibility remains unverified; see docs/data_access.md. |
| 4.2d | Prepare bounded study-area extracts from large local GIS downloads | Complete | 2026-11-08 | src/sources/extract.py, prepare_extract.py and automatic lineage checks implemented. 128 tests pass; FileGDB/ZIP/native-coordinate/cap/scope/corruption checks and four-source PostGIS distances pass. CLI inspect/prepare/repeat/failure preserves flags/other entries; original is hashed, not cached. Actual ST37 compatibility/performance unverified. See docs/regional_extracts.md. |
| 4.3a | Implement cache, provenance, atomic load/analyze and attempt history | Complete | 2026-11-08 | 80 tests pass overall; simulated-source repeats preserve one run, partial acquisition/DB failures preserve previous data, transfer/record caps and checksum validation tested. |
| 4.3b | Execute and validate an official-data small-region run | In progress | 2026-11-08 | Unrun pending actual service/download access and verified source mappings; no real AER/provincial/federal result has been produced. |
| 5.1 | Verify Petrinex access, reporting level, identifiers and licensing | Out of scope | 2026-11-08 | User removed Petrinex/monthly production; no actual download, production mapping or real refresh is required for the revised project. |
| 5.2 | Implement monthly production ingestion and defensible joins | Out of scope | 2026-11-08 | User removed Petrinex/monthly production; no actual download, production mapping or real refresh is required for the revised project. |
| 5.3 | Legacy: Validate production chart or explicit unavailable/facility-level display (outside current scope) | Complete | 2026-11-08 | Verified-only monthly chart, separate product/activity/unit series, explicit synthetic label and unavailable other-well message passed Python and real browser checks; facility volume remains audit-only. |
| 5.2a | Legacy: Implement production contracts/import, exact-ID audit and refresh history (outside current scope) | Complete | 2026-11-08 | Synthetic fixture: 9 inputs, 6 accepted, 2 quarantined, 1 outside window; verified/facility/unmatched/unknown and ambiguous cases tested. Repeats reuse a batch; forced failures retain prior active data. |
| 5.2c | Legacy: Import configured local production CSV/ZIP with provenance and refresh audit (outside current scope) | Complete | 2026-11-08 | Local CSV/ZIP imports use immutable bytes and preserve original download-date provenance; synthetic integration checks verify exact links, facility audit, repeat batches, failure retention and actual AppTest refresh/chart. Included in 113 passing tests; actual Petrinex mapping remains open. |
| 5.2b | Verify actual Petrinex mapping and execute a bounded real refresh | Out of scope | 2026-11-08 | User removed Petrinex/monthly production; no actual download, production mapping or real refresh is required for the revised project. |
| 5.4 | Verify AER surface-hole fields, identifiers and status/location meaning | In progress | 2026-11-08 | Guide provides candidate fields; inspect actual FileGDB/converted CSV schema, CRS and key uniqueness before enabling. |
| 5.5 | Validate real AER well attributes in the detail panel and exports | Not started | 2026-11-08 | Requires a bounded actual AER input and verified mapping; no monthly production chart required. |
| 6.1 | Validate performance, locking, idempotency and failed-run recovery | Complete | 2026-11-08 | src/db/workflow.py and integration crash/concurrency/export-failure tests; 118 tests and both offline browser checks pass. Synthetic 1,000 wells/30 features: first 0.2953 s, repeat 0.1851 s, dashboard/export 0.0534 s. Scope/limits in docs/release_verification.md. |
| 6.2 | Complete methodology, provenance, limitations and course evidence | In progress | 2026-11-08 | Current implementation/recovery/limitations docs and separate course indexes updated (6.2a). Actual-source provenance, final results/interpretation and submission evidence remain open (6.2b). |
| 6.3 | Verify fresh-clone demo, handoff and separate course packages | In progress | 2026-11-08 | Isolated candidate clone, new venv, new DB and offline demo/browser checks passed (6.3a). Exact final Git commit/user platform verification and final course packages remain open (6.3b). |
| 6.2a | Update implementation/recovery documentation and separate course evidence indexes | Complete | 2026-11-08 | docs/limitations.md, release_verification.md, retained code/evidence hashes and AIDA-1145/AIDA-2362 EVIDENCE.md link current methods, checks and remaining actual-data deliverables. |
| 6.2b | Complete actual-data provenance, interpretation and final course evidence | Not started | 2026-11-08 | Requires verified source inputs/results from Phases 4–5; no final findings or course submission claimed. |
| 6.3a | Verify isolated candidate checkout with fresh dependencies and offline demo | Complete | 2026-11-08 | Local clone of 98d2904 plus candidate overlay; new Python 3.12 venv with 67 pinned packages, new DB, 118 tests, repeated setup/demo CLI and both offline Chromium checks passed. Test DB/app cleaned up; durable summary in docs/evidence/release_verification_2026-11-08.json. |
| 6.3c | Document local-project setup and post-download completion checklist | Complete | 2026-11-08 | docs/download_inputs.md includes local software/database/.env setup, private catalogue inspection/mapping, chained extract preparation, PostGIS ingest, app catalogue/study alignment, real-data QA/reruns/exports/tests and course handoff checkboxes. Instructions checked against current CLI/config; actual local deployment and real-data acceptance are still open. |
| 6.3b | Verify final committed checkout/user platform and prepare final course packages | Not started | 2026-11-08 | Candidate remains uncommitted in this pass; repeat checkout smoke at final commit, check intended platform, finish permitted output/screenshot/presentation/review packages and current D2L requirements. |

### Progress log

| Date | Step / phase | Update |
|---|---|---|
| 2026-11-08 | 0.1, 1.1 | Recorded completed onboarding inspection and environment setup; application implementation remains unfinished. |
| 2026-11-08 | D.1 | Converted the Word design to Markdown, preserved its scope and tables, and added phase/substep tracking and ongoing update instructions. |
| 2026-11-08 | 0.2–1.5 | Started application configuration, architecture, database migrations, synthetic demo, contracts, setup documentation and repository tests. |
| 2026-11-08 | 0, 1 | Completed configuration/architecture, migrations, synthetic fixtures, spatial contracts, quarantine, manifests and setup docs. Clean pinned venv: 32 tests passed without skips/warnings; setup and repeated demo verified from outside the checkout. Phase 2 can use synthetic inputs; no new credential or source decision is needed for its distance engine. |
| 2026-11-08 | 2.1–2.2 | Started spatial calculations, explicit coverage handling, cumulative flags and baseline/sensitivity tests. |
| 2026-11-08 | Source scope clarification | Recorded the user-supplied dataset reference and real-data target stack, including optional wetlands/2014 ESA and basemap-only OpenStreetMap. Acquisition metadata/permissions remain unverified; no live ingestion is claimed. |
| 2026-11-08 | 2 | Completed spatial engine and explicit coverage handling. 61 tests passed without skips/warnings; demo analysis records 10 well/category rows and a 2-to-1 water threshold sensitivity result. Real-source intent/catalogue clarified from the supplied reference. |
| 2026-11-08 | 3.1–3.3 | Started Streamlit workflow, map, stable-ID details, filters and filtered exports. |
| 2026-11-08 | 3 | Completed offline Streamlit workflow/map, stable record-reference selection, filters, quality/history and matching exports. 67 Python tests passed; real Chromium smoke passed including standalone HTML. Fixed component plain-text ID handling and isolated HTML export from the displayed figure. Saved app startup and tile-domain draft requirement; online tiles remain unverified pending settings. |
| 2026-11-08 | 4.1–4.3 | Started official-source verification and bounded acquisition/cache/provenance implementation. |
| 2026-11-08 | 4 (partial) | Implemented bounded acquisition framework, inspection/CLI, caches, bundles, live feature margin, transactionally published spatial data, readiness gates and attempt audit. 80 Python tests and offline browser smoke pass on synthetic inputs. Official discovery remains blocked by CONNECT 403; saved four required domains in the draft, preserving prior settings. Phase 4 is not complete. Published OSM tile permission separately verified with HTTP 200. |
| 2026-11-08 | 5.1–5.3 | Started independent production contracts/import/linking/UI work. Phase 4 access is still unapplied; Phase 5 official reporting semantics/licensing must also be verified before real production can be shown. |
| 2026-11-08 | 5 (partial) | Implemented production contracts, CSV/ZIP import, exact unique namespace matching, ambiguity/facility/unmatched audit, immutable batches, transactional refresh and UI chart. 103 Python tests plus map and production browser smoke pass. Synthetic demo is labelled; real Petrinex access/semantics and real refresh remain blocked, so Phase 5 is not complete. |
| 2026-11-08 | 4.1a | Resumed official-source discovery in the newly published environment. Published host permissions are applied; prior blanket CONNECT-denial status is superseded. Catalogue/resource verification is in progress; no environment changes or publication requested. |
| 2026-11-08 | 4.1a complete; 4/5 partial | Located official parks service/licence metadata, current Petrinex public pages, download host/API pattern and documented reporting/masking/identifier limits. Added response hash evidence and metadata-only catalogue updates. Actual GIS/production hosts remain denied; AER HTTP 403 and Canada HTTP 429 differ from proxy denial. 25 targeted configuration/production-contract tests pass, including the partial-metadata enablement gate. No real data loaded or environment settings changed/published. |
| 2026-11-08 | D.2; 4.2c planned | User confirmed eventual runtime API/download access may differ from cloud access. Documented remote/direct-download/local-file routes and preserved intended sources. Local-file ingestion is a separate Not started step; current local production inspector does not establish full import support. Cloud domain changes are not a prerequisite for eventual runtime validation. |
| 2026-11-08 | 4.2c, 5.2c | Started local-file acquisition, coordinate-mapped well CSV, catalogue selection and provenance for spatial/production pipelines. Testing will use labelled synthetic files; official compatibility is still unverified. |
| 2026-11-08 | 4.2c, 5.2c complete; Phases 4/5 partial | Implemented local snapshots, coordinate well CSV, GIS/GeoJSON and production CSV/ZIP, runtime catalogue selection, local inspection and disabled template. Full suite: 113 passed, no skips; synthetic offline spatial/production integration and AppTest refresh/chart verified. No official data acquired or environment published. Source-specific verification and a bounded real-data run remain open. |
| 2026-11-08 | 6.1–6.3 started | Starting database-wide workflow concurrency/recovery validation, bounded performance checks, isolated-checkout offline demo and handoff evidence cleanup. Official input/schema validation remains open. |
| 2026-11-08 | 6.1, 6.2a, 6.3a complete; Phase 6 partial | Added full-workflow DB advisory lock, busy UI and interrupted-attempt recovery. 118 tests pass in the final new isolated environment; killed-process and report-write failures retain committed data. Synthetic 1,000-well benchmark recorded; fresh candidate clone/new dependencies/new DB/repeated CLI and both offline Chromium checks pass. Updated limitations and separate course indexes. Final committed-platform check, real-data interpretation and final course packages remain open; no environment settings changed or published. |
| 2026-11-08 | 4.1b / scope revision | Reviewed all four ST37 guide pages, verified its printed duplicate BH_Latitude label, documented surface/bottom/string grain and archive-cap issue. User removed Petrinex; Phase 5 now covers AER attributes. Default app/catalogues omit production and retain legacy code/data. All data/ ignored; manual download instructions and environmental catalogue candidates recorded.  Current scope checks: 118 tests and the offline default map/browser smoke pass, with production buttons absent; config follow-up 10 tests pass. See docs/evidence/current_scope_2026-11-08.json. |
| 2026-11-08 | 4.2d started | User chose a smaller-extract workflow for growing ST37 archives. Preparing regional GIS packages without caching/copying the full original, while retaining parent-input provenance and bounded app/database imports. |
| 2026-11-08 | 4.2d complete | Implemented local regional preparation with streamed parent provenance, native geometry/selected fields, bounded small ZIP, deterministic bytes, atomic publish/reuse and scope/mapping/data checks. 128 tests pass; edge distances 50/100 m and failed wider-area retry verified in PostGIS. CLI synthetic 2,153,063-byte original produces a 4,940-byte two-record package without enabling sources. Whole download/hashing still scales with original size; actual ST37 remains untested. |
| 2026-11-08 | 4.1c, 6.3c complete | Consolidated website links and explicit file choices in the download checklist; fresh metadata confirms habitat FGDB ZIP versus water/parks REST/KML references. Added post-download local-project steps and remaining real-data/platform/handoff checks. Documentation/link/command checks completed; no code, runtime configuration or source verification flags changed. |

Prioritize a small, demonstrable end-to-end vertical slice before importing all Alberta wells. Build source adapters as replaceable modules so a format or service change does not require rewriting the UI or spatial analysis.

## 14. Course evidence and final handoff

AIDA 1145: contracts, source inventory and permissions, raw/cleaned schema, extraction/transform/load code, quarantine, run manifest, SQL tables, test results and reproducibility report. AIDA 2362: CRS evidence, spatial methodology, threshold sensitivity table, map screenshots/exports, company comparison, limitations and an interpretation report. Preserve approved research questions and update project-charter.md and scope-matrix.md. Instructor repository notes indicate distinct D2L packages and a December 7, 2026 deadline; verify exact D2L requirements. User confirms OpenStreetMap replaces QGIS for this implementation.

## 15. Codex kickoff instruction (paste with this document)

You are implementing the attached Alberta Oil Well Environmental Screening design in my existing GitHub repository. First inspect README.md, project-charter.md, scope-matrix.md and both course READMEs. Do not delete or restructure existing course evidence. Implement Phase 0 and Phase 1 only first. Write complete commented code, beginner-friendly setup steps for Windows, .env.example, SQL migrations, synthetic fixtures, and pytest tests. Do not invent dataset field names or URLs; use source_catalog.yml placeholders where not verified and report the missing details. Preserve the ability to run a demo without internet. After Phase 1, show files changed, exact commands to run, test results, and what you need from me before Phase 2. Never commit secrets or large source datasets.

## 16. Open decisions and verification checklist

- [x] Choose first Alberta study region and geographic boundary; make it configurable.
- [ ] Confirm current AER distribution format, field mapping, CRS, file size and permitted use.
- [ ] Confirm exact ArcGIS REST service URLs/layer IDs and any paging/geometry limits; avoid guessing.
- [x] Remove Petrinex/monthly production from required scope — user decision 2026-11-08; default catalogues/UI exclude it.
- [ ] Confirm whether environmental layers may be redistributed or must be fetched at runtime.
- [ ] Confirm desired presentation style and whether optional wetlands/ESA should be deferred until after first successful release.

References: supplied “Alberta Environmental Datasets Reference v2”, “Final Project Proposal AIDA 1145/2362”, and uploaded project repository ZIP (README, charter, scope and course folders). Public source endpoints must be rechecked during implementation; no unverified URLs are treated as stable contracts.
