"""Atomic nearest-feature calculations on run-scoped PostGIS geometries."""
from uuid import UUID

from pydantic import Field
from sqlalchemy import Engine, text
from typing import Literal

from src.config import StrictModel
from src.contracts.spatial import CATEGORIES


class Coverage(StrictModel):
    status: Literal['complete','incomplete','unavailable']
    note: str = Field(min_length=1)


def demo_coverage(incomplete_categories: set[str] | None = None) -> dict[str, Coverage]:
    # A deliberately closed synthetic world, not a claim about real Alberta data.
    result = {}
    for category in CATEGORIES:
        if category not in ('water','protected_area'):
            status, note = 'unavailable', 'This category is not supplied by the demo fixture.'
        elif category in (incomplete_categories or set()):
            status, note = 'incomplete', 'At least one input feature was quarantined; coverage cannot be declared complete.'
        else:
            status, note = 'complete', 'Synthetic fixture defines all features in this category (including the 500 m search margin).'
        result[category] = Coverage(status=status,note=note)
    return result


NEAREST_SQL = '''
INSERT INTO screening.well_proximity
    (run_id,well_pk,category,nearest_feature_pk,distance_m,coverage_status)
SELECT :run, w.well_pk, c.category, nearest.feature_pk, nearest.distance_m, c.status
FROM screening.wells w
JOIN screening.source_snapshots ws ON ws.snapshot_id=w.snapshot_id AND ws.run_id=:run
CROSS JOIN screening.category_coverage c
LEFT JOIN LATERAL (
    SELECT f.feature_pk, ST_Distance(w.geom,f.geom) AS distance_m
    FROM screening.environmental_features f
    JOIN screening.source_snapshots fs ON fs.snapshot_id=f.snapshot_id AND fs.run_id=:run
    WHERE c.status='complete' AND f.feature_type=c.category
      AND ST_DWithin(w.geom,f.geom,500)
    ORDER BY ST_Distance(w.geom,f.geom), f.source_feature_id COLLATE "C", f.source_key,
             f.snapshot_id, f.feature_pk
    LIMIT 1
) nearest ON true
WHERE c.run_id=:run
'''

RESULTS_SQL = '''
SELECT p.well_pk, w.source_well_id, p.category, p.coverage_status, c.note AS coverage_note,
    f.source_feature_id AS nearest_feature_id, p.distance_m,
    p.within_50, p.within_100, p.within_250, p.within_500,
    CASE WHEN p.coverage_status <> 'complete' THEN p.coverage_status
         WHEN p.distance_m IS NULL THEN 'no_feature_within_500m' ELSE 'matched' END AS result_state
FROM screening.well_proximity p
JOIN screening.wells w ON w.well_pk=p.well_pk
JOIN screening.category_coverage c ON c.run_id=p.run_id AND c.category=p.category
LEFT JOIN screening.environmental_features f ON f.feature_pk=p.nearest_feature_pk
WHERE p.run_id=:run
ORDER BY w.source_well_id, w.well_pk, p.category
'''


def analyze_run(engine: Engine, run_id: str, coverage: dict[str, Coverage] | None = None) -> list[dict]:
    """Rebuild a run's proximity results in one transaction, preserving prior rows on error.

    One row per well/category includes an explicit known-negative or unknown
    outcome, so wells without a nearby feature are not silently removed. The
    parent-row lock serializes analyses of the same run.
    """
    run = UUID(str(run_id))
    if coverage is not None and any(category not in CATEGORIES for category in coverage):
        raise ValueError('Unknown environmental category in coverage')
    overrides = {key: Coverage.model_validate(value) for key, value in (coverage or {}).items()}
    with engine.begin() as conn:
        record = conn.execute(text('SELECT status,study_area FROM screening.pipeline_runs WHERE run_id=:run FOR UPDATE'),
                              {'run':run}).mappings().one_or_none()
        if record is None or record['status'] not in ('seeded','succeeded'):
            raise ValueError('Spatial analysis requires an existing seeded run')
        if record['study_area'].get('analysis_crs') != 'EPSG:3400' or record['study_area'].get('thresholds_m') != [50,100,250,500]:
            raise ValueError('Spatial analysis requires EPSG:3400 and the standard 50/100/250/500 metre thresholds')
        count = conn.execute(text('''SELECT count(*) FROM screening.wells w
            JOIN screening.source_snapshots s ON s.snapshot_id=w.snapshot_id WHERE s.run_id=:run'''),
                             {'run':run}).scalar_one()
        if not count:
            raise ValueError('Run has no accepted wells to analyze')
        conn.execute(text('DELETE FROM screening.well_proximity WHERE run_id=:run'), {'run':run})
        for category in sorted(CATEGORIES):
            entry = overrides.get(category)
            if entry:
                conn.execute(text('''INSERT INTO screening.category_coverage VALUES (:run,:category,:status,:note)
                    ON CONFLICT (run_id,category) DO UPDATE SET status=excluded.status,note=excluded.note'''),
                             {'run':run,'category':category,**entry.model_dump()})
            else:
                conn.execute(text('''INSERT INTO screening.category_coverage VALUES
                    (:run,:category,'unavailable','Coverage has not been verified for this run.')
                    ON CONFLICT (run_id,category) DO NOTHING'''), {'run':run,'category':category})
        conn.execute(text(NEAREST_SQL), {'run':run})
        rows = conn.execute(text(RESULTS_SQL), {'run':run}).mappings().all()
        if len(rows) != count * len(CATEGORIES):
            raise ValueError('Spatial result row accounting failed')
        return [dict(row) for row in rows]


def read_results(engine: Engine, run_id: str) -> list[dict]:
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(text(RESULTS_SQL), {'run':UUID(str(run_id))}).mappings()]
