"""Compare an explicit ST37 snapshot with a stored provincial hydrography layer."""
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text

from src.db.migrations import migrate
from src.db.st37 import st37_import_snapshots
from src.db.workflow import serialized_workflow
from src.sources.waterbodies import PROVINCE_SCOPE, PROVINCE_SCOPES, PROVINCE_STREAM_SCOPE

STREAM_COMPARISON_CODES = ('STR-PER', 'CANAL', 'OXBOW-PER', 'DITCH')
WELL_MAP_BATCH_SIZE = 10_000

@serialized_workflow
def compare_st37_waterbodies(engine, st37_import_id: UUID, water_import_id: UUID) -> UUID:
    migrate(engine)
    with engine.begin() as conn:
        wells = conn.execute(text('''SELECT accepted_count,coordinate_crs,crs_evidence
            FROM screening.st37_imports WHERE import_id=:id'''), {'id': st37_import_id}).mappings().one_or_none()
        if not wells or not wells['coordinate_crs'] or not wells['crs_evidence'] or not wells['accepted_count']:
            raise ValueError('Select an ST37 import with accepted wells and verified coordinate evidence')
        water = conn.execute(text('''SELECT feature_count,manifest->>'scope' AS scope
            FROM screening.water_imports WHERE import_id=:id'''), {'id': water_import_id}).mappings().one_or_none()
        if not water or water['scope'] not in PROVINCE_SCOPES or not water['feature_count']:
            raise ValueError('Select a province-wide waterbody or stream import with accepted features')
        stream_codes = list(STREAM_COMPARISON_CODES) if water['scope'] == PROVINCE_STREAM_SCOPE else None
        comparison_id = uuid5(NAMESPACE_URL, f'alberta-waterbody-comparison-v1:{st37_import_id}:{water_import_id}')
        new = conn.execute(text('''INSERT INTO screening.waterbody_comparisons
            (comparison_id,st37_import_id,water_import_id,well_count)
            VALUES (:id,:st37,:water,:count) ON CONFLICT (comparison_id) DO NOTHING RETURNING comparison_id'''),
            {'id': comparison_id, 'st37': st37_import_id, 'water': water_import_id,
             'count': wells['accepted_count']}).scalar_one_or_none()
        if new is not None:
            conn.execute(text('''INSERT INTO screening.st37_waterbody_proximity
                (comparison_id,source_row,nearest_source_feature_id,observed_distance_m)
                SELECT :id,w.source_row,near.source_feature_id,near.distance_m
                FROM screening.st37_surface_holes w
                LEFT JOIN LATERAL (
                    SELECT b.source_feature_id, ST_Distance(w.geom,b.geom) AS distance_m
                    FROM screening.water_features b
                    WHERE b.import_id=:water AND ST_DWithin(b.geom,w.geom,500)
                        AND (CAST(:codes AS text[]) IS NULL OR b.feature_type_code=ANY(CAST(:codes AS text[])))
                    ORDER BY distance_m,b.source_feature_id COLLATE "C" LIMIT 1
                ) near ON true
                WHERE w.import_id=:st37 AND w.geom IS NOT NULL'''),
                {'id': comparison_id, 'st37': st37_import_id, 'water': water_import_id, 'codes': stream_codes})
        actual = conn.execute(text('''SELECT count(*) FROM screening.st37_waterbody_proximity
            WHERE comparison_id=:id'''), {'id': comparison_id}).scalar_one()
        if actual != wells['accepted_count']:
            raise ValueError('Every accepted ST37 record needs a verified point before comparison can be published')
        return comparison_id


def latest_province_waterbodies(engine):
    with engine.connect() as conn:
        if not conn.execute(text("SELECT to_regclass('screening.waterbody_comparisons')")).scalar_one():
            return None
        row = conn.execute(text('''SELECT w.import_id,w.feature_count,w.quarantined_count,w.coverage_status,
            (SELECT c.comparison_id FROM screening.waterbody_comparisons c WHERE c.water_import_id=w.import_id
             ORDER BY c.compared_at DESC,c.comparison_id DESC LIMIT 1) AS comparison_id
            FROM screening.water_imports w WHERE manifest->>'scope'=:scope
            ORDER BY w.imported_at DESC,w.import_id DESC LIMIT 1'''), {'scope': PROVINCE_SCOPE}).mappings().one_or_none()
        return dict(row) if row else None


def waterbody_workflow_snapshots(engine) -> tuple[list[dict], list[dict]]:
    """Return inventory headers for the app, including database versions before migration 007."""
    with engine.connect() as conn:
        wells = st37_import_snapshots(conn)
        has_water = conn.execute(text("SELECT to_regclass('screening.water_imports') IS NOT NULL")).scalar_one()
        water = conn.execute(text('''SELECT import_id,imported_at,feature_count,quarantined_count,coverage_status,
            manifest->>'scope' AS scope FROM screening.water_imports WHERE (manifest->>'scope')=ANY(:scopes)
            ORDER BY imported_at DESC,import_id DESC'''), {'scopes': list(PROVINCE_SCOPES)}).mappings() if has_water else ()
        return wells, [dict(row) for row in water]


def find_waterbody_comparison(engine, st37_import_id: UUID, water_import_id: UUID) -> UUID | None:
    with engine.connect() as conn:
        if not conn.execute(text("SELECT to_regclass('screening.waterbody_comparisons')")).scalar_one():
            return None
        return conn.execute(text('''SELECT comparison_id FROM screening.waterbody_comparisons
            WHERE st37_import_id=:st37 AND water_import_id=:water'''),
            {'st37': st37_import_id, 'water': water_import_id}).scalar_one_or_none()


def st37_water_comparisons(engine, st37_import_id: UUID) -> list[dict]:
    """List the stored water comparisons for this exact well snapshot."""
    with engine.connect() as conn:
        if not conn.execute(text("SELECT to_regclass('screening.waterbody_comparisons')")).scalar_one():
            return []
        return [dict(row) for row in conn.execute(text('''SELECT c.comparison_id,
            w.import_id,w.imported_at,w.feature_count,w.coverage_status,w.manifest->>'scope' AS scope
            FROM screening.waterbody_comparisons c
            JOIN screening.water_imports w ON w.import_id=c.water_import_id
            WHERE c.st37_import_id=:st37
            ORDER BY w.imported_at DESC,w.import_id DESC'''), {'st37': st37_import_id}).mappings()]


def waterbody_comparison_summary(engine, comparison_id: UUID) -> dict:
    with engine.connect() as conn:
        row = conn.execute(text('''SELECT c.comparison_id,c.st37_import_id,c.water_import_id,c.well_count,
            w.coverage_status,w.feature_count,w.quarantined_count,w.manifest->>'scope' AS scope,
            count(*) FILTER (WHERE p.observed_distance_m<=50) AS within_50,
            count(*) FILTER (WHERE p.observed_distance_m<=100) AS within_100,
            count(*) FILTER (WHERE p.observed_distance_m<=250) AS within_250,
            count(*) FILTER (WHERE p.observed_distance_m<=500) AS within_500,
            count(*) FILTER (WHERE p.observed_distance_m IS NULL AND w.coverage_status='complete') AS no_feature_within_500,
            count(*) FILTER (WHERE p.observed_distance_m IS NULL AND w.coverage_status='incomplete') AS unknown_within_500
            FROM screening.waterbody_comparisons c
            JOIN screening.water_imports w ON w.import_id=c.water_import_id
            JOIN screening.st37_waterbody_proximity p ON p.comparison_id=c.comparison_id
            WHERE c.comparison_id=:id
            GROUP BY c.comparison_id,w.import_id'''), {'id': comparison_id}).mappings().one_or_none()
        if row is None:
            raise ValueError('Waterbody comparison was not found')
        summary = dict(row)
        if summary['scope'] == PROVINCE_SCOPE:
            summary['no_polygon_within_500'] = summary['no_feature_within_500']
        return summary


def waterbody_map_batch(engine, comparison_id: UUID, seed: int, offset: int = 0,
                        limit: int = WELL_MAP_BATCH_SIZE, *, licence: str = '',
                        excluded_rows: tuple[int, ...] = ()) -> tuple[list[dict], list[dict]]:
    """Read a shuffled page or an exact licence and its matching display geometries."""
    if offset < 0 or not 1 <= limit <= WELL_MAP_BATCH_SIZE:
        raise ValueError('A map batch must contain between 1 and 10,000 wells')
    with engine.connect() as conn:
        # Page the narrow proximity rows before loading well attributes or geometries.
        licence_filter = '''AND p.source_row IN (
            SELECT s.source_row FROM screening.waterbody_comparisons c
            JOIN screening.st37_surface_holes s ON s.import_id=c.st37_import_id
            WHERE c.comparison_id=:id AND s.well_licence_number=:licence
        )''' if licence else ''
        boundary_filter = 'AND p.source_row <> ALL(:excluded_rows)' if excluded_rows else ''
        wells = [dict(row) for row in conn.execute(text(f'''WITH batch AS MATERIALIZED (
                SELECT p.source_row, p.observed_distance_m, p.nearest_source_feature_id,
                    CAST(md5(CAST(:seed AS text) || ':' || p.source_row) AS uuid) AS shuffle_key
                FROM screening.st37_waterbody_proximity p
                WHERE p.comparison_id=:id {licence_filter} {boundary_filter}
                ORDER BY shuffle_key, p.source_row LIMIT :limit OFFSET :offset
            )
            SELECT s.source_row, s.well_licence_number, b.observed_distance_m, b.nearest_source_feature_id,
                CAST(ST_AsGeoJSON(ST_Transform(s.geom,4326),6) AS jsonb) AS geometry
            FROM batch b
            JOIN screening.waterbody_comparisons c ON c.comparison_id=:id
            JOIN screening.st37_surface_holes s ON s.import_id=c.st37_import_id AND s.source_row=b.source_row
            ORDER BY b.shuffle_key, b.source_row'''),
            {'id': comparison_id, 'seed': seed, 'offset': offset, 'limit': limit, 'licence': licence,
             'excluded_rows': list(excluded_rows)}).mappings()]
        feature_ids = sorted({row['nearest_source_feature_id'] for row in wells
                              if row['nearest_source_feature_id'] is not None})
        if not feature_ids:
            return wells, []
        # These simplified shapes are for display. Distances come from the stored comparison.
        water = [dict(row) for row in conn.execute(text('''SELECT b.source_feature_id, b.name,
                CAST(ST_AsGeoJSON(ST_Transform(ST_SimplifyPreserveTopology(b.geom,25),4326),6) AS jsonb) AS geometry
            FROM screening.waterbody_comparisons c
            JOIN screening.water_imports w ON w.import_id=c.water_import_id
            JOIN screening.water_features b ON b.import_id=w.import_id AND b.source_key=w.manifest->>'source_key'
            WHERE c.comparison_id=:id AND b.source_feature_id=ANY(:features)
            ORDER BY b.source_feature_id'''), {'id': comparison_id, 'features': feature_ids}).mappings()]
        return wells, water


def waterbody_result(engine, comparison_id: UUID, licence: str) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(text('''SELECT s.well_licence_number,s.licensee_name,s.licence_status,
            s.legal_location,s.surface_latitude,s.surface_longitude,i.coordinate_crs,
            p.nearest_source_feature_id,b.name AS nearest_waterbody,b.feature_type_code,
            p.observed_distance_m,w.coverage_status,
            CASE WHEN p.observed_distance_m IS NOT NULL THEN 'observed_match'
                 WHEN w.coverage_status='incomplete' THEN 'unknown_incomplete_coverage'
                 WHEN w.manifest->>'scope'=:streams THEN 'no_stream_within_500'
                 ELSE 'no_polygon_within_500' END AS result_state
            FROM screening.waterbody_comparisons c
            JOIN screening.water_imports w ON w.import_id=c.water_import_id
            JOIN screening.st37_imports i ON i.import_id=c.st37_import_id
            JOIN screening.st37_surface_holes s ON s.import_id=c.st37_import_id
            JOIN screening.st37_waterbody_proximity p ON p.comparison_id=c.comparison_id AND p.source_row=s.source_row
            LEFT JOIN screening.water_features b ON b.import_id=w.import_id
                AND b.source_key=w.manifest->>'source_key' AND b.source_feature_id=p.nearest_source_feature_id
            WHERE c.comparison_id=:id AND s.well_licence_number=:licence'''),
            {'id': comparison_id, 'licence': licence.strip(), 'streams': PROVINCE_STREAM_SCOPE}).mappings().one_or_none()
        return dict(row) if row is not None else None
