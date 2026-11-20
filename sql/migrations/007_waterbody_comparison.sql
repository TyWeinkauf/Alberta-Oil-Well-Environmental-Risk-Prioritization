-- Province-wide layer-72 snapshots and water-only comparisons share existing inventories.
CREATE TABLE screening.water_feature_rejects (
    import_id uuid NOT NULL REFERENCES screening.water_imports,
    source_key text NOT NULL,
    source_feature_id text NOT NULL,
    reason_code text NOT NULL,
    reason_detail text NOT NULL,
    payload jsonb NOT NULL,
    PRIMARY KEY (import_id, source_key, source_feature_id)
);

CREATE TABLE screening.waterbody_comparisons (
    comparison_id uuid PRIMARY KEY,
    st37_import_id uuid NOT NULL REFERENCES screening.st37_imports,
    water_import_id uuid NOT NULL REFERENCES screening.water_imports,
    compared_at timestamptz NOT NULL DEFAULT now(),
    well_count integer NOT NULL CHECK (well_count > 0),
    UNIQUE (st37_import_id, water_import_id)
);

CREATE TABLE screening.st37_waterbody_proximity (
    comparison_id uuid NOT NULL REFERENCES screening.waterbody_comparisons,
    source_row integer NOT NULL CHECK (source_row >= 2),
    nearest_source_feature_id text,
    observed_distance_m double precision,
    PRIMARY KEY (comparison_id, source_row),
    CHECK ((nearest_source_feature_id IS NULL AND observed_distance_m IS NULL) OR
           (nearest_source_feature_id IS NOT NULL AND observed_distance_m IS NOT NULL
               AND observed_distance_m BETWEEN 0 AND 500))
);

COMMENT ON TABLE screening.st37_waterbody_proximity IS
    'Observed distance to the nearest accepted layer-72 polygon within 500 m. Interpret with the water import coverage status.';
