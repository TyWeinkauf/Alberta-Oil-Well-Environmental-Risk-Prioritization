-- Coverage is an explicit assertion, never inferred from a missing spatial match.
CREATE TABLE screening.category_coverage (
    run_id uuid NOT NULL REFERENCES screening.pipeline_runs,
    category text NOT NULL CHECK (category IN ('water','protected_area','critical_habitat','wetland','esa')),
    status text NOT NULL CHECK (status IN ('complete','incomplete','unavailable')),
    note text NOT NULL CHECK (btrim(note) <> ''),
    PRIMARY KEY (run_id, category)
);
ALTER TABLE screening.well_proximity
    ADD COLUMN coverage_status text NOT NULL DEFAULT 'unavailable'
    CHECK (coverage_status IN ('complete','incomplete','unavailable'));

-- Preserve unknown flags for unverified coverage; complete coverage without a
-- candidate within 500 m is a known negative, not an unknown observation.
ALTER TABLE screening.well_proximity
    DROP COLUMN within_50, DROP COLUMN within_100,
    DROP COLUMN within_250, DROP COLUMN within_500;
ALTER TABLE screening.well_proximity
    ADD COLUMN within_50 boolean GENERATED ALWAYS AS
        (CASE WHEN coverage_status='complete' THEN coalesce(distance_m <= 50,false) END) STORED,
    ADD COLUMN within_100 boolean GENERATED ALWAYS AS
        (CASE WHEN coverage_status='complete' THEN coalesce(distance_m <= 100,false) END) STORED,
    ADD COLUMN within_250 boolean GENERATED ALWAYS AS
        (CASE WHEN coverage_status='complete' THEN coalesce(distance_m <= 250,false) END) STORED,
    ADD COLUMN within_500 boolean GENERATED ALWAYS AS
        (CASE WHEN coverage_status='complete' THEN coalesce(distance_m <= 500,false) END) STORED,
    ADD CONSTRAINT proximity_feature_distance_pair CHECK
        ((nearest_feature_pk IS NULL) = (distance_m IS NULL));
