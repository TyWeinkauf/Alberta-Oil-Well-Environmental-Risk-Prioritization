"""Consistent, read-only dashboard snapshots; no data loading on widget reruns."""
import json
from uuid import UUID

from sqlalchemy import Engine, text

from src.spatial.engine import RESULTS_SQL


def pipeline_attempts(engine: Engine) -> list[dict]:
    with engine.connect() as conn:
        if conn.execute(text("SELECT to_regclass('screening.pipeline_attempts')")).scalar_one() is None:
            return []
        rows=conn.execute(text('''SELECT attempt_id,started_at,finished_at,status,stage,run_id,error_code,error_summary
            FROM screening.pipeline_attempts ORDER BY started_at DESC LIMIT 50''')).mappings()
        return [{key:(value.isoformat() if hasattr(value,'isoformat') else str(value) if isinstance(value,UUID) else value)
                 for key,value in row.items()} for row in rows]


def list_analyzed_runs(engine: Engine) -> list[dict]:
    with engine.connect() as conn:
        records = conn.execute(text('''
            SELECT r.run_id,r.started_at,r.study_area FROM screening.pipeline_runs r
            WHERE r.status IN ('seeded','succeeded')
              AND (SELECT count(*) FROM screening.wells w JOIN screening.source_snapshots s
                   ON s.snapshot_id=w.snapshot_id WHERE s.run_id=r.run_id)>0
              AND (SELECT count(*) FROM screening.well_proximity p WHERE p.run_id=r.run_id) =
                  5*(SELECT count(*) FROM screening.wells w JOIN screening.source_snapshots s
                     ON s.snapshot_id=w.snapshot_id WHERE s.run_id=r.run_id)
            ORDER BY r.started_at DESC,r.run_id DESC
        ''')).mappings()
        return [{'run_id':str(row['run_id']),'started_at':row['started_at'].isoformat(),
                 'study_area':row['study_area']} for row in records]


def load_dashboard(engine: Engine, run_id: str) -> dict:
    run = UUID(run_id)
    # All queries see one database snapshot even if another session recalculates.
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
        info = conn.execute(text('SELECT * FROM screening.pipeline_runs WHERE run_id=:run'),{'run':run}).mappings().one()
        wells = conn.execute(text('''
            SELECT w.well_pk,w.source_well_id,w.licensee_name,w.uwi_if_available,
                w.operator_name_if_verified,w.lsd_text,w.status,
                ST_X(ST_Transform(w.geom,4326)) AS longitude,
                ST_Y(ST_Transform(w.geom,4326)) AS latitude,s.source_key,s.checksum,
                s.retrieved_at,s.native_crs
            FROM screening.wells w JOIN screening.source_snapshots s ON s.snapshot_id=w.snapshot_id
            WHERE s.run_id=:run ORDER BY w.source_well_id,w.well_pk
        '''),{'run':run}).mappings().all()
        proximity = conn.execute(text(RESULTS_SQL),{'run':run}).mappings().all()
        if not wells or len(proximity) != len(wells)*5:
            raise ValueError('This run does not have a complete spatial result set; run analysis first')
        features = conn.execute(text('''
            SELECT f.source_feature_id,f.feature_type,f.name,ST_AsGeoJSON(ST_Transform(f.geom,4326)) AS geometry
            FROM screening.environmental_features f JOIN screening.source_snapshots s ON s.snapshot_id=f.snapshot_id
            WHERE s.run_id=:run ORDER BY f.feature_type,f.source_feature_id
        '''),{'run':run}).mappings().all()
        snapshots = conn.execute(text('''SELECT source_key,url,retrieved_at,checksum,license_note,native_crs,record_count
            FROM screening.source_snapshots WHERE run_id=:run ORDER BY source_key'''),{'run':run}).mappings().all()
        quarantine = conn.execute(text('''SELECT source_key,record_reference,reason_code,reason_detail,raw_payload_reference
            FROM screening.quarantine_records WHERE run_id=:run ORDER BY source_key,record_reference'''),{'run':run}).mappings().all()
        coverage = conn.execute(text('SELECT category,status,note FROM screening.category_coverage WHERE run_id=:run ORDER BY category'),
                                {'run':run}).mappings().all()
        return {
            'run_id':run_id,'started_at':info['started_at'].isoformat(),'study_area':info['study_area'],
            'ingestion_status':info['status'],'analysis_status':'analyzed','config_hash':info['config_hash'],
            'wells':[{**dict(row),'retrieved_at':row['retrieved_at'].isoformat()} for row in wells],
            'proximity':[dict(row) for row in proximity],
            'features':[{**dict(row),'geometry':json.loads(row['geometry'])} for row in features],
            'sources':[{**dict(row),'retrieved_at':row['retrieved_at'].isoformat()} for row in snapshots],
            'quarantine':[dict(row) for row in quarantine],'coverage':[dict(row) for row in coverage],
        }
