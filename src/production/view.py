"""Read the active batch only; verified well charts and facility audits stay separate."""
from uuid import UUID

from sqlalchemy import text


def production_view(engine,run_id: str,well_pk: int | None=None) -> dict:
    run=UUID(str(run_id))
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
        if conn.execute(text("SELECT to_regclass('screening.production_active')")).scalar_one() is None:
            return {'batch':None,'verified':[],'audit':[],'quarantine':[]}
        batch=conn.execute(text('''SELECT b.*,s.source_key,s.url,s.retrieved_at,s.checksum FROM screening.production_active a
            JOIN screening.production_batches b ON b.batch_id=a.batch_id AND b.run_id=a.run_id
            JOIN screening.source_snapshots s ON s.snapshot_id=b.snapshot_id WHERE a.run_id=:run'''),{'run':run}).mappings().one_or_none()
        if batch is None:return {'batch':None,'verified':[],'audit':[],'quarantine':[]}
        result={'batch':{**dict(batch),'batch_id':str(batch['batch_id']),'run_id':str(batch['run_id']),
                         'snapshot_id':str(batch['snapshot_id'])},'verified':[],'audit':[],'quarantine':[]}
        if well_pk is not None:
            valid=conn.execute(text('''SELECT 1 FROM screening.wells w JOIN screening.source_snapshots s ON s.snapshot_id=w.snapshot_id
                WHERE w.well_pk=:well AND s.run_id=:run'''),{'well':well_pk,'run':run}).first()
            if not valid:raise ValueError('Selected well does not belong to this analysis run')
            rows=conn.execute(text('''SELECT p.source_record_id,p.period,p.product,p.activity,p.volume,p.unit,
                    p.reporting_facility_id,l.join_method,l.evidence
                FROM screening.production_monthly p JOIN screening.production_well_links l ON l.production_pk=p.production_pk
                JOIN screening.production_link_audit a ON a.production_pk=p.production_pk AND a.batch_id=:batch
                WHERE p.snapshot_id=:snapshot AND l.well_pk=:well AND l.confidence_status='verified'
                    AND a.link_status='verified' AND p.attribution_level='well' ORDER BY p.period,p.source_record_id'''),
                {'batch':batch['batch_id'],'snapshot':batch['snapshot_id'],'well':well_pk}).mappings()
            result['verified']=[{**dict(row),'period':row['period'].strftime('%Y-%m'),'volume':str(row['volume'])} for row in rows]
        audits=conn.execute(text('''SELECT p.source_record_id,p.period,p.product,p.activity,p.volume,p.unit,
                p.reporting_facility_id,p.well_identifier_nullable,p.attribution_level,a.link_status,a.reason_code,a.candidate_count
            FROM screening.production_monthly p JOIN screening.production_link_audit a ON a.production_pk=p.production_pk
            WHERE a.batch_id=:batch ORDER BY p.period,p.source_record_id'''),{'batch':batch['batch_id']}).mappings()
        result['audit']=[{**dict(row),'period':row['period'].strftime('%Y-%m'),'volume':str(row['volume'])} for row in audits]
        result['quarantine']=[dict(row) for row in conn.execute(text('''SELECT record_reference,reason_code,reason_detail,raw_payload_reference
            FROM screening.production_quarantine WHERE batch_id=:batch ORDER BY record_reference'''),{'batch':batch['batch_id']}).mappings()]
        for key,value in list(result['batch'].items()):
            if hasattr(value,'isoformat'):result['batch'][key]=value.isoformat()
        return result
