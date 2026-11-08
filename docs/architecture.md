# Architecture

## Implemented foundation (Phases 0–1)

`src/config.py` reads strict YAML contracts. Study extents use WGS84 bounds; stored geometries use EPSG:3400 metres. The configured bounding box is a broad synthetic test extent, not a chosen real study area. Unknown or incomplete live-source metadata stays disabled. Credentials come from `DATABASE_URL` or an ignored root `.env`; process bindings take precedence.

`scripts/setup_db.py` applies numbered SQL files through `src/db/migrations.py`. PostgreSQL 17/PostGIS is required. Migrations share a transaction and advisory lock; the `screening.schema_migrations` ledger records SHA-256 checksums. Repeated setup is a no-op; changing an applied file is an error. Existing data is never reset automatically.

`scripts/demo_seed.py` calls `src/db/demo.py`:

1. Read project-authored fixture bytes, check version/provenance, validate the CRS and all records.
2. Compute fixture/config hashes and a deterministic run UUID including the contract version.
3. Archive exact bytes under `data/raw/<sha256>/demo.json`; verify an existing copy instead of overwriting it.
4. Acquire a database transaction lock and insert one run/snapshot, accepted wells/features and explicit quarantine references. A failed load rolls back the whole transaction. Identity sequence gaps after rollback are harmless.
5. Mark the run `seeded` and commit. Repeated ingestion verifies existing counts and reuses the same run. Different fixture/config versions create independent runs/snapshots; cross-version history is intentional.
6. Atomically write validation/manifest files under `outputs/runs/<run_id>/`. A report-write failure leaves database rows intact and can be retried by running the command again.

IDs are unique within an entity and source snapshot. All occurrences of a duplicate source ID are quarantined, rather than choosing an arbitrary first occurrence. Validation preserves optional null fields, keeps original licensee labels and adds a normalized exact search label. It does not fuzzy-merge companies, guess a CRS or repair invalid polygons. Phase 1 requires geometries wholly inside the demo extent; later adapters must implement the specified 500 m environmental margin.

The quarantine record stores a reason and a raw-file/row reference. Raw files are generated artifacts; don't commit real source records by following the synthetic fixture example. Phase 1 errors before commit produce no partial run in application tables; persistent failed-run audit logging is planned with the later orchestrator.

## Implemented spatial engine (Phase 2)

`scripts/analyze_demo.py` seeds the fixture and calls `src/spatial/engine.py`. Migration 002 adds explicit run/category coverage and coverage-aware flags. `ST_DWithin` limits candidates to 500 m; `ST_Distance` and stable source-ID tie-breaking choose a nearest actual geometry for each well/category. Both wells and features are scoped to the same run. Parent-row locking and a single transaction preserve previous results if recalculation fails.

Five rows per well retain matched, known-negative, unavailable and incomplete outcomes. `src/spatial/classification.py` recomputes overall bands from selected categories, keeps unknown coverage distinct from known negatives and compares baseline/changed selections. Analysis JSON is separate from the ingestion manifest. Reseeding preserves analysis unless newly detected coverage gaps invalidate it. See [spatial methodology](spatial_methodology.md).

## Implemented presentation (Phase 3)

`app.py` presents workflow, map/results, data quality and session history. `src/orchestrator.py` runs the demo only on an explicit action. Widget reruns use `src/ui/data.py` to load a read-only REPEATABLE READ snapshot, so table/map/source details agree even during another session's recalculation. Only datasets with complete result-row accounting are selectable.

`src/ui/model.py` applies the shared spatial classification plus company/status/known-match filters. This single filtered list drives markers, metrics, table and `src/exports/selection.py` CSV/GeoJSON. Marker popup text carries a stable record reference through the component event bridge; selection never uses coordinates as a key. `src/ui/map.py` escapes source text, embeds licensed local library assets and builds an independent map for standalone export, because streamlit-folium mutates its displayed figure.

The app retains selection outside filters with an explicit message. Production remains unavailable rather than fabricated. Live pipeline/production controls are disabled until adapters exist. Offline geometry is the default; optional OpenStreetMap tiles need network access. See [UI workflow](ui_workflow.md).

## Acquisition framework (Phase 4 in progress)

`src/sources/http.py` caches exact response bytes with SHA-256, conditional refresh, retry and response/total transfer caps. `src/sources/files.py` inspects ZIP Shapefile/GPKG/FileGDB layers and their actual CRS before bounded reads. `src/sources/arcgis.py` inspects metadata, queries count/IDs for the buffered extent, pages by object ID and rejects incomplete results. Inspection and execution are separate CLI commands.

`src/sources/pipeline.py` requires verified core sources/coverage, acquires and validates all inputs, archives canonical records alongside exact response lineage, and uses one transaction for source/well/feature/quarantine insertion plus shared `calculate_proximity`. It writes the run manifest before marking/committing the dataset succeeded. Failed acquisitions/loads retain the previous published data; attempts persist stage/error class through migration 003. A filesystem artifact left by a failed database commit is not proof of a published run.

Live features are clipped to the projected study polygon plus 500 m after geometry validation; exact tangent intersections retain valid original geometry so inclusive boundary matches are not lost. The UI enables the live action only when the catalogue is ready and labels data according to demo/live mode. Current official entries remain disabled: publisher/source verification is blocked on network access. See [source verification](source_verification.md).

## Production foundation (Phase 5 in progress)

`src/production/contracts.py` validates canonical month/product/activity/unit/decimal/reporting-level records and resolves only exact documented identifiers. `csv_source.py` applies configured CSV columns/value/period mappings; these are not assumptions about current Petrinex fields. `store.py` imports immutable batches with link audits and quarantines, then atomically switches an active pointer. Changed inputs/window/identifier evidence create a new revision; unchanged repeats reuse one. Failed imports retain previous active data, and real refresh failures persist a redacted attempt stage/error class.

`view.py` serves active, run-scoped, well-level verified links only. `ui.py` separates product/activity/unit chart series and keeps facility/unmatched/ambiguous/unknown rows in the audit. Synthetic production is explicitly labelled and prohibited on real-source runs; real refresh requires a real-source run. Migration 004 separates snapshot role/revision metadata and production batch/audit tables. See [production](production.md). Official access, licence, grain and identifier verification remain blocked on network settings.

## Planned components

The design's future flow is **Streamlit → orchestrator → source adapters → raw cache → contracts/quarantine → staging/PostGIS → spatial SQL → map/results/exports**. Download/transform work must run only on explicit actions, outside Streamlit rerun side effects.

- **Remaining Phase 4:** verify official AER/provincial/federal URLs, fields, CRS, terms and scope, then complete and validate an actual small-region ingestion. Simulated protocol tests do not establish official compatibility.
- **Remaining Phase 5:** inspect actual Petrinex product/licence/schema and reporting level, verify identifier compatibility with actual well data, then execute a bounded real refresh. Facility totals remain excluded from well charts.
- **Phase 6:** performance, cancellation/recovery, last-successful-run publication, clean-clone app demonstration and separate course handoffs.

Production storage is populated only through its explicit verified-source or labelled synthetic import; proximity rows are populated by the analysis command. `seeded` describes ingestion, and the separate report's `analyzed` status describes the spatial calculation without claiming full application publication. Live source integration will use the real-data stack recorded in [the supplied reference](dataset_reference.md). App-level acceptance remains tracked in `DESIGN.md`.
