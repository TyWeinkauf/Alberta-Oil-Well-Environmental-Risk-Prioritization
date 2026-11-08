-- Preserve immutable production refresh history without replacing spatial inputs.
ALTER TABLE screening.source_snapshots
    ADD COLUMN revision_key text NOT NULL DEFAULT '',
    ADD COLUMN source_role text NOT NULL DEFAULT 'analysis' CHECK (source_role IN ('analysis','production','basemap')),
    DROP CONSTRAINT source_snapshots_run_id_source_key_key,
    ADD CONSTRAINT source_snapshot_revision_unique UNIQUE (run_id,source_key,revision_key);

CREATE TABLE screening.production_batches (
    batch_id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES screening.pipeline_runs,
    snapshot_id uuid NOT NULL UNIQUE REFERENCES screening.source_snapshots,
    imported_at timestamptz NOT NULL DEFAULT now(),
    source_mode text NOT NULL CHECK (source_mode IN ('synthetic','live')),
    window_start date NOT NULL,
    window_end date NOT NULL CHECK (window_end>=window_start),
    source_identity text NOT NULL,
    configuration jsonb NOT NULL,
    validation jsonb NOT NULL,
    UNIQUE (run_id,batch_id)
);
CREATE TABLE screening.production_active (
    run_id uuid PRIMARY KEY REFERENCES screening.pipeline_runs,
    batch_id uuid NOT NULL,
    FOREIGN KEY (run_id,batch_id) REFERENCES screening.production_batches(run_id,batch_id)
);
CREATE TABLE screening.production_link_audit (
    production_pk bigint PRIMARY KEY REFERENCES screening.production_monthly,
    batch_id uuid NOT NULL REFERENCES screening.production_batches,
    link_status text NOT NULL CHECK (link_status IN ('verified','unmatched','ambiguous','facility','unknown')),
    reason_code text NOT NULL,
    candidate_count integer NOT NULL CHECK (candidate_count>=0)
);
CREATE TABLE screening.production_quarantine (
    batch_id uuid NOT NULL REFERENCES screening.production_batches,
    record_reference text NOT NULL,
    reason_code text NOT NULL,
    reason_detail text NOT NULL,
    raw_payload_reference text NOT NULL,
    PRIMARY KEY (batch_id,record_reference)
);
CREATE INDEX production_snapshot_period_idx ON screening.production_monthly(snapshot_id,period);
