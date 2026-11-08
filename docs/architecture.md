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

## Planned components

The design's future flow is **Streamlit → orchestrator → source adapters → raw cache → contracts/quarantine → staging/PostGIS → spatial SQL → map/results/exports**. Download/transform work must run only on explicit actions, outside Streamlit rerun side effects.

- **Phase 3:** Folium/streamlit-folium map, stable-ID click selection, filters, accessible result table and matching exports. OpenStreetMap is a basemap, not a distance source.
- **Phase 4:** verified AER/ArcGIS/federal source adapters, checksummed snapshots, coverage, retries and bounded live ingestion. URLs and source field mappings must be verified, not inferred from this fixture.
- **Phase 5:** production contracts/adapters and documented well-level joins. Facility totals must never be allocated to wells without source evidence.
- **Phase 6:** performance, cancellation/recovery, last-successful-run publication, clean-clone app demonstration and separate course handoffs.

Production storage remains empty; proximity rows are populated by the analysis command. `seeded` describes ingestion, and the separate report's `analyzed` status describes the spatial calculation without claiming full application publication. Live source integration will use the real-data stack recorded in [the supplied reference](dataset_reference.md). App-level acceptance remains tracked in `DESIGN.md`.
