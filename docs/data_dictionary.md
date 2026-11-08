# Data dictionary

All project tables are in `screening`. Geometry storage is EPSG:3400; output maps will transform to EPSG:4326 in later phases. Table/column definitions and constraints are authoritative in the numbered files under `sql/migrations/`.

| Table | Grain / keys | Important fields |
|---|---|---|
| schema_migrations | One applied SQL file; filename PK | checksum, applied_at; editing applied history is rejected |
| pipeline_runs | One fixture/config/contract version; run_id UUID PK | started_at, finished_at, status, study_area JSON, config_hash, error_summary |
| source_snapshots | One source within a run; snapshot_id UUID PK; unique run_id/source_key | URL/reference, timestamp, SHA-256, license_note, native_crs, input record_count |
| wells | One accepted well in a snapshot; well_pk PK; unique snapshot_id/source_well_id | Original/normalized licensee, nullable UWI/operator/LSD/status, required Point geometry |
| environmental_features | One accepted feature in a snapshot; feature_pk PK; unique snapshot_id/source_feature_id | source_key, feature_type, nullable name, line/polygon geometry |
| quarantine_records | One rejected input row per run/source; quarantine_pk PK | zero-based entity/row reference, deterministic reason_code/detail, raw_payload_reference |
| production_monthly | One accepted monthly observation; unique snapshot_id/source_record_id | period (first day of month), product, activity, volume, unit, attribution_level; synthetic or verified real batch, with exact decimal volume |
| production_well_links | Well/production pair PK | join_method, evidence, confidence_status; chart queries use verified links and active-batch audit only |
| well_proximity | One run/well/category PK | nearest feature, distance_m within 500 m, coverage_status, generated cumulative within_50/100/250/500 flags |
| pipeline_attempts | One attempted real-source workflow; attempt_id UUID PK | start/finish, running/succeeded/failed, stage, optional published run_id, error class and redacted summary |
| category_coverage | One run/category PK | complete/incomplete/unavailable status and explanation; explicit coverage, not inferred from match presence |

Run statuses currently used are `loading` inside a transaction and `seeded` after successful ingestion. `succeeded`, `failed` and `cancelled` are reserved for later orchestration. A separate analysis report uses `analyzed`. Migration 002 makes flags false for complete coverage with no feature within 500 m, and null for incomplete/unavailable coverage. Source completeness must be verified at real-data acquisition time in Phase 4.

## Fixture and validation accounting

`tests/fixtures/demo.json` is manually authored synthetic data with CRS metadata, a version, provenance text, 7 well records and 3 feature records. No identifier or company represents a real well or operator. Geometry is GeoJSON-shaped but projected; its explicit document-level CRS is required. This is an internal fixture format, not an assumption about any official source format.

| Outcome | Count | Explanation |
|---|---|---|
| Accepted wells | 2 | Valid point IDs and locations; optional fields may be null |
| Accepted environmental features | 2 | One synthetic stream line and one protected-area polygon |
| Rejected wells | 5 | Both duplicate-ID rows, one missing ID, one missing geometry, one outside-extent point |
| Rejected environmental features | 1 | Self-intersecting polygon |
| Total | 10 | 4 accepted + 6 quarantined; no silently dropped records |

Other row-level reasons include unsupported geometry type, malformed geometry, invalid/nonfinite coordinates, invalid text-field type and unsupported feature category. Missing/unknown document CRS rejects the whole batch before any run is loaded. Geometry repair is deliberately not automatic.

`manifest.json` contains run ID/status, config hash, study area, source checksum/reference/timestamp/CRS/permission, database counts and validation results. `validation.json` contains input/accepted/rejected counts, reason frequencies and each rejected row reference. Resolve `<raw file>#wells/2` as the third entry of the archived document's `wells` list. Raw snapshot bytes allow the retained source licensee label to be traced even when a search label is normalized.

## Live acquisition (not yet verified against official sources)

Source bundles preserve request/final URLs, raw-byte checksums, original retrieval times, conditional HTTP metadata, inspected CRS/layer/fields and canonical selected-record references. PostGIS source retrieval timestamps come from those responses, not merely the latest pipeline execution time. Snapshot checksum identifies the archived source bundle; bundle raw-response entries retain the original download/page checksums. Record grain is the bounded acquired subset. The live manifest records content identities, input/accepted/rejected accounting, quality reasons and coverage. Real-field mappings and actual source compatibility remain unverified; see `source_verification.md`.

## Production batch/audit metadata

Migration 004 adds `source_snapshots.source_role` and `revision_key`, retaining spatial revisions while allowing immutable production snapshots. Production has no CRS and is labelled not applicable (tabular). `production_batches` records run/snapshot, synthetic/live source mode, month window, content/evidence identity, configuration and validation accounting. `production_active` is a run-scoped pointer; historical batches never double-count into a current chart. `production_link_audit` records verified/unmatched/ambiguous/facility/unknown status, reason and candidate count per observation. `production_quarantine` records rejected CSV record references and reasons by batch.

The synthetic production fixture has 9 input records: 6 accepted, 2 quarantined and 1 outside the window. Three records have verified synthetic well links; facility, unmatched and unknown-level observations are retained separately. Canonical fields and the 38-digit/12-decimal technical numeric contract are documented in `production.md`. Actual Petrinex fields/grain remain unverified. Spatial input validation counts exclude production-role snapshots so the grains do not mix.
