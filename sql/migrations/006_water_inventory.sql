-- Water-only imports remain separate from complete four-source screening runs.
CREATE TABLE screening.water_imports (
    import_id uuid PRIMARY KEY,
    imported_at timestamptz NOT NULL DEFAULT now(),
    study_area jsonb NOT NULL,
    manifest jsonb NOT NULL,
    feature_count integer NOT NULL CHECK (feature_count >= 0),
    quarantined_count integer NOT NULL CHECK (quarantined_count >= 0),
    coverage_status text NOT NULL CHECK (coverage_status IN ('complete','incomplete'))
);
CREATE TABLE screening.water_features (
    import_id uuid NOT NULL REFERENCES screening.water_imports,
    source_key text NOT NULL,
    source_feature_id text NOT NULL,
    name text,
    feature_type_code text,
    properties jsonb NOT NULL,
    geom geometry(Geometry,3400) NOT NULL CHECK (
        NOT ST_IsEmpty(geom) AND ST_IsValid(geom)
        AND GeometryType(geom) IN ('LINESTRING','MULTILINESTRING','POLYGON','MULTIPOLYGON')),
    PRIMARY KEY (import_id,source_key,source_feature_id)
);
CREATE INDEX water_inventory_geom_idx ON screening.water_features USING gist (geom);
COMMENT ON TABLE screening.water_features IS
    'Study-area water inventory with 500 m environmental margin. Does not publish well screening results or establish survey accuracy.';
