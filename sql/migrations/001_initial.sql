-- The screening schema is separate from any other local database applications.
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE screening.pipeline_runs (
    run_id uuid PRIMARY KEY,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    status text NOT NULL CHECK (status IN ('loading','seeded','succeeded','failed','cancelled')),
    study_area jsonb NOT NULL,
    config_hash text NOT NULL CHECK (length(config_hash) = 64),
    error_summary text
);
COMMENT ON COLUMN screening.pipeline_runs.status IS
    'Phase 1 uses seeded: ingestion is complete but spatial analysis/publication has not run.';

CREATE TABLE screening.source_snapshots (
    snapshot_id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES screening.pipeline_runs,
    source_key text NOT NULL,
    url text NOT NULL,
    retrieved_at timestamptz NOT NULL DEFAULT now(),
    checksum text NOT NULL CHECK (length(checksum) = 64),
    license_note text NOT NULL,
    native_crs text NOT NULL,
    record_count integer NOT NULL CHECK (record_count >= 0),
    UNIQUE (run_id, source_key)
);

CREATE TABLE screening.wells (
    well_pk bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_well_id text NOT NULL CHECK (btrim(source_well_id) <> ''),
    uwi_if_available text,
    licensee_name text,
    licensee_search text,
    operator_name_if_verified text,
    lsd_text text,
    status text,
    geom geometry(Point,3400) NOT NULL CHECK (NOT ST_IsEmpty(geom) AND ST_IsValid(geom)),
    snapshot_id uuid NOT NULL REFERENCES screening.source_snapshots,
    UNIQUE (snapshot_id, source_well_id)
);
CREATE INDEX wells_geom_idx ON screening.wells USING gist (geom);
CREATE INDEX wells_id_idx ON screening.wells (source_well_id);
CREATE INDEX wells_company_idx ON screening.wells (licensee_search);

CREATE TABLE screening.environmental_features (
    feature_pk bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_key text NOT NULL,
    feature_type text NOT NULL CHECK (feature_type IN ('water','protected_area','critical_habitat','wetland','esa')),
    source_feature_id text NOT NULL CHECK (btrim(source_feature_id) <> ''),
    name text,
    geom geometry(Geometry,3400) NOT NULL CHECK (
        NOT ST_IsEmpty(geom) AND ST_IsValid(geom)
        AND GeometryType(geom) IN ('LINESTRING','MULTILINESTRING','POLYGON','MULTIPOLYGON')
    ),
    snapshot_id uuid NOT NULL REFERENCES screening.source_snapshots,
    UNIQUE (snapshot_id, source_feature_id)
);
CREATE INDEX features_geom_idx ON screening.environmental_features USING gist (geom);

-- Production storage is reserved here; ingestion and verified joins are Phase 5.
CREATE TABLE screening.production_monthly (
    production_pk bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_record_id text NOT NULL,
    reporting_facility_id text,
    well_identifier_nullable text,
    period date NOT NULL CHECK (extract(day FROM period) = 1),
    product text NOT NULL,
    activity text NOT NULL,
    volume numeric NOT NULL,
    unit text NOT NULL,
    attribution_level text NOT NULL CHECK (attribution_level IN ('well','facility','unknown')),
    snapshot_id uuid NOT NULL REFERENCES screening.source_snapshots,
    UNIQUE (snapshot_id, source_record_id)
);
CREATE INDEX production_period_idx ON screening.production_monthly (period);
CREATE TABLE screening.production_well_links (
    well_pk bigint NOT NULL REFERENCES screening.wells,
    production_pk bigint NOT NULL REFERENCES screening.production_monthly,
    join_method text NOT NULL,
    evidence text NOT NULL,
    confidence_status text NOT NULL CHECK (confidence_status IN ('verified','ambiguous','unverified')),
    PRIMARY KEY (well_pk, production_pk)
);
CREATE TABLE screening.well_proximity (
    run_id uuid NOT NULL REFERENCES screening.pipeline_runs,
    well_pk bigint NOT NULL REFERENCES screening.wells,
    category text NOT NULL,
    nearest_feature_pk bigint REFERENCES screening.environmental_features,
    distance_m double precision CHECK (distance_m >= 0 AND distance_m < 'Infinity'::float8),
    within_50 boolean GENERATED ALWAYS AS (distance_m <= 50) STORED,
    within_100 boolean GENERATED ALWAYS AS (distance_m <= 100) STORED,
    within_250 boolean GENERATED ALWAYS AS (distance_m <= 250) STORED,
    within_500 boolean GENERATED ALWAYS AS (distance_m <= 500) STORED,
    PRIMARY KEY (run_id, well_pk, category)
);
CREATE TABLE screening.quarantine_records (
    quarantine_pk bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES screening.pipeline_runs,
    source_key text NOT NULL,
    record_reference text NOT NULL,
    reason_code text NOT NULL,
    reason_detail text NOT NULL,
    raw_payload_reference text NOT NULL,
    UNIQUE (run_id, source_key, record_reference)
);
