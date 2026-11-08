CREATE TABLE screening.pipeline_attempts (
    attempt_id uuid PRIMARY KEY,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    status text NOT NULL CHECK (status IN ('running','succeeded','failed')),
    stage text NOT NULL,
    study_area jsonb NOT NULL,
    run_id uuid REFERENCES screening.pipeline_runs,
    error_code text,
    error_summary text
);
CREATE INDEX pipeline_attempts_started_idx ON screening.pipeline_attempts (started_at DESC);
CREATE INDEX features_snapshot_category_idx ON screening.environmental_features (snapshot_id,feature_type);
CREATE INDEX snapshots_run_idx ON screening.source_snapshots (run_id);
