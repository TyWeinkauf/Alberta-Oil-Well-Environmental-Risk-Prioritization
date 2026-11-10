-- Unpublished source inventory. No pipeline run or environmental coverage is implied.
CREATE TABLE screening.st37_imports (
    import_id uuid PRIMARY KEY,
    imported_at timestamptz NOT NULL DEFAULT now(),
    content_identity text NOT NULL CHECK (length(content_identity) = 64),
    source_checksum text NOT NULL CHECK (length(source_checksum) = 64),
    inventory_checksum text NOT NULL CHECK (length(inventory_checksum) = 64),
    source_metadata jsonb NOT NULL,
    coordinate_crs text,
    crs_evidence text,
    license_note text NOT NULL CHECK (btrim(license_note) <> ''),
    downloaded_at timestamptz,
    release_date date,
    record_count integer NOT NULL CHECK (record_count > 0),
    accepted_count integer NOT NULL CHECK (accepted_count >= 0),
    quarantined_count integer NOT NULL CHECK (quarantined_count >= 0),
    CHECK (record_count = accepted_count + quarantined_count),
    CHECK ((coordinate_crs IS NULL AND crs_evidence IS NULL)
        OR (coordinate_crs IS NOT NULL AND btrim(crs_evidence) <> ''))
);

CREATE TABLE screening.st37_surface_holes (
    import_id uuid NOT NULL REFERENCES screening.st37_imports,
    source_row integer NOT NULL CHECK (source_row >= 2),
    well_licence_number text NOT NULL,
    licensee_name text,
    licence_status text,
    licence_status_date date,
    ground_elevation double precision,
    spud_date date,
    most_recent_final_drill_date date,
    energy_development_category text,
    legal_location text,
    surface_latitude double precision,
    surface_longitude double precision,
    validation_errors jsonb NOT NULL CHECK (jsonb_typeof(validation_errors) = 'array'),
    quality_warnings jsonb NOT NULL CHECK (jsonb_typeof(quality_warnings) = 'array'),
    raw_payload jsonb NOT NULL,
    geom geometry(Point,3400),
    PRIMARY KEY (import_id, source_row),
    CHECK (geom IS NULL OR (ST_IsValid(geom) AND NOT ST_IsEmpty(geom)
                           AND validation_errors = '[]'::jsonb))
);
CREATE INDEX st37_inventory_licence_idx ON screening.st37_surface_holes (well_licence_number);
CREATE INDEX st37_inventory_licensee_idx ON screening.st37_surface_holes (licensee_name);
CREATE INDEX st37_inventory_geom_idx ON screening.st37_surface_holes USING gist (geom);
COMMENT ON TABLE screening.st37_surface_holes IS
    'Unpublished AER surface-hole inventory. Invalid rows retained with errors; geometry requires a documented geographic CRS. Not a completed environmental screening run.';
