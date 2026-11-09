"""Immutable production batches, exact-ID audit and atomic active-batch changes."""
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import text

from src.db.workflow import serialized_workflow

from src.artifacts import write_json
from src.config import ROOT, Source, load_source_catalog
from src.db.migrations import migrate
from src.production.contracts import month, resolve_link, validate_production
from src.production.csv_source import read_csv
from src.sources.http import HttpCache
from src.sources.local import acquire_snapshot


def production_requirements(source: Source | None) -> list[str]:
    if source is None or source.role!='production' or not source.enabled or not source.verified:
        return ['Production source, licence, reporting level and field mapping are not verified/enabled.']
    required={'source_record_id','period','product','activity','volume','unit'}
    missing=required-source.field_mapping.keys()
    errors=[f'Production mapping is missing {sorted(missing)}'] if missing else []
    if source.reporting_level=='mixed' and ('attribution_level' not in source.field_mapping or not source.attribution_values):
        errors.append('Mixed reporting requires an explicit source-level mapping and value translation.')
    return errors


@serialized_workflow
def import_csv(engine,run_id: str,path: Path,source: Source,*,start: str,end: str,synthetic: bool=False,
               retrieved_at: str | None=None,raw_root: Path | None=None,output_root: Path | None=None,
               max_records: int=100000, acquisition: dict | None=None) -> dict:
    if not synthetic:
        errors=production_requirements(source)
        if errors:raise ValueError('; '.join(errors))
    if path.stat().st_size>512*1024**2:
        raise ValueError('Production input exceeds the 512 MiB file cap')
    with path.open('rb') as handle:
        payload=handle.read(512*1024**2+1)
    if len(payload)>512*1024**2:
        raise ValueError('Production input exceeds the 512 MiB file cap')
    checksum=hashlib.sha256(payload).hexdigest()
    archive=(raw_root or ROOT/'data/raw/production')/checksum/'source_payload'
    archive.parent.mkdir(parents=True,exist_ok=True)
    try:
        with archive.open('xb') as handle:handle.write(payload)
    except FileExistsError:
        if archive.read_bytes()!=payload:raise ValueError('Immutable production snapshot checksum mismatch') from None
    rows=read_csv(archive,source,max_records=max_records)
    validation=validate_production(rows,source,start,end)
    if not validation.accepted and validation.rejected:
        raise ValueError('No acceptable production records; the previous batch must be retained')
    migrate(engine)
    run=UUID(str(run_id))
    with engine.begin() as conn:
        info=conn.execute(text('SELECT study_area,status FROM screening.pipeline_runs WHERE run_id=:run FOR UPDATE'),
                          {'run':run}).mappings().one_or_none()
        if info is None or info['status'] not in ('seeded','succeeded'):
            raise ValueError('Production requires an existing loaded analysis run')
        if synthetic and info['study_area']['mode']!='demo':
            raise ValueError('Synthetic production must never be attached to a real-source analysis run')
        if not synthetic and info['study_area']['mode']!='live':
            raise ValueError('Real production requires a real-source analysis run')
        wells=conn.execute(text('''SELECT w.well_pk,w.source_well_id,w.uwi_if_available,s.source_key
            FROM screening.wells w JOIN screening.source_snapshots s ON s.snapshot_id=w.snapshot_id
            WHERE s.run_id=:run ORDER BY s.source_key,w.source_well_id,w.well_pk'''),{'run':run}).mappings().all()
        candidates=defaultdict(list)
        if source.well_identifier_field:
            for well in wells:
                value=well[source.well_identifier_field]
                if value:candidates[value.strip()].append(well['well_pk'])
        fingerprint=[{k:w[k] for k in ('source_key','source_well_id','uwi_if_available')} for w in wells]
        configuration={'source':source.model_dump(mode='json'),'start':start,'end':end,
                       'well_identifiers':fingerprint,'contract_version':1,'synthetic':synthetic}
        identity=hashlib.sha256((checksum+json.dumps(configuration,sort_keys=True,separators=(',',':'))).encode()).hexdigest()
        batch=uuid5(run,'production:'+identity);snapshot=uuid5(batch,source.key)
        existing=conn.execute(text('SELECT validation FROM screening.production_batches WHERE batch_id=:batch'),
                              {'batch':batch}).scalar_one_or_none()
        if existing is None:
            stats={'input_records':validation.input_records,'accepted':len(validation.accepted),
                   'quarantined':len(validation.rejected),'excluded_outside_window':validation.excluded_records,
                   'reason_counts':dict(Counter(r['reason_code'] for r in validation.rejected)),
                   'link_status_counts':{}}
            conn.execute(text('''INSERT INTO screening.source_snapshots
                (snapshot_id,run_id,source_key,url,retrieved_at,checksum,license_note,native_crs,record_count,revision_key,source_role)
                VALUES (:snapshot,:run,:key,:url,:retrieved,:sha,:note,'not applicable (tabular)',:count,:revision,'production')'''),
                {'snapshot':snapshot,'run':run,'key':source.key,'url':str(source.url or source.metadata_url or '') if not synthetic else 'fixture:'+str(path),
                 'retrieved':datetime.fromisoformat(retrieved_at) if retrieved_at else datetime.now(timezone.utc),
                 'sha':checksum,'note':source.license_note or 'Project-authored synthetic production fixture only',
                 'count':len(rows),'revision':identity})
            conn.execute(text('''INSERT INTO screening.production_batches
                (batch_id,run_id,snapshot_id,source_mode,window_start,window_end,source_identity,configuration,validation)
                VALUES (:batch,:run,:snapshot,:mode,:start,:end,:identity,CAST(:config AS jsonb),CAST(:stats AS jsonb))'''),
                {'batch':batch,'run':run,'snapshot':snapshot,'mode':'synthetic' if synthetic else 'live',
                 'start':month(start),'end':month(end),'identity':identity,'config':json.dumps(configuration),'stats':json.dumps(stats)})
            counts=Counter()
            for row in validation.accepted:
                production_pk=conn.execute(text('''INSERT INTO screening.production_monthly
                    (snapshot_id,source_record_id,reporting_facility_id,well_identifier_nullable,period,product,activity,volume,unit,attribution_level)
                    VALUES (:snapshot,:source_record_id,:reporting_facility_id,:well_identifier_nullable,:period,:product,:activity,:volume,:unit,:attribution_level)
                    RETURNING production_pk'''),{'snapshot':snapshot,**row}).scalar_one()
                status,reason,matched=resolve_link(row,candidates,source);counts[status]+=1
                conn.execute(text('INSERT INTO screening.production_link_audit VALUES (:pk,:batch,:status,:reason,:count)'),
                             {'pk':production_pk,'batch':batch,'status':status,'reason':reason,'count':len(matched)})
                for key in matched:
                    conn.execute(text('''INSERT INTO screening.production_well_links
                        (well_pk,production_pk,join_method,evidence,confidence_status)
                        VALUES (:well,:pk,'exact_identifier',:evidence,:confidence)'''),
                        {'well':key,'pk':production_pk,'evidence':f'{source.identifier_namespace}: {source.join_evidence}',
                         'confidence':'verified' if status=='verified' else 'ambiguous'})
            for row in validation.rejected:
                conn.execute(text('''INSERT INTO screening.production_quarantine
                    VALUES (:batch,:record_reference,:reason_code,:reason_detail,:raw)'''),
                    {'batch':batch,'raw':str(archive)+'#'+row['record_reference'],**row})
            stats['link_status_counts']=dict(counts)
            conn.execute(text('UPDATE screening.production_batches SET validation=CAST(:stats AS jsonb) WHERE batch_id=:batch'),
                         {'stats':json.dumps(stats),'batch':batch})
        else:stats=existing
        stored=conn.execute(text('SELECT count(*) FROM screening.production_monthly WHERE snapshot_id=:snapshot'),
                            {'snapshot':snapshot}).scalar_one()
        audited=conn.execute(text('SELECT count(*) FROM screening.production_link_audit WHERE batch_id=:batch'),
                             {'batch':batch}).scalar_one()
        quarantined=conn.execute(text('SELECT count(*) FROM screening.production_quarantine WHERE batch_id=:batch'),
                                 {'batch':batch}).scalar_one()
        if stored!=stats['accepted'] or audited!=stored or quarantined!=stats['quarantined']:
            raise ValueError('Stored production batch counts differ from validated input; refusing to activate it')
        conn.execute(text('''INSERT INTO screening.production_active VALUES (:run,:batch)
            ON CONFLICT (run_id) DO UPDATE SET batch_id=excluded.batch_id'''),{'run':run,'batch':batch})
        report={'run_id':str(run),'batch_id':str(batch),'status':'imported','source_mode':'synthetic' if synthetic else 'live',
                'source_key':source.key,'acquisition':acquisition,'raw_sha256':checksum,'raw_payload_reference':str(archive),
                'configuration':configuration,'validation':stats,
                'disclaimer':'Only exact, uniquely verified well-level links may populate a well production chart. Facility volumes are never allocated.'}
        write_json((output_root or ROOT/'outputs/runs')/str(run)/'production'/str(batch)/'manifest.json',report)
    return report


@serialized_workflow
def refresh_production(engine,run_id: str,*,start: str,end: str,source: Source | None=None,
                       cache: HttpCache | None=None,refresh: bool=True,**kwargs) -> dict:
    if month(start)>month(end):raise ValueError('Production window start must not follow its end')
    if source is None:
        source=next((s for s in load_source_catalog().sources if s.key=='petrinex_production'),None)
    errors=production_requirements(source)
    if errors:raise ValueError('Production source preflight blocked: '+'; '.join(errors))
    migrate(engine)
    run=UUID(str(run_id));attempt=uuid4();stage='production:acquire'
    with engine.begin() as conn:
        area=conn.execute(text('SELECT study_area FROM screening.pipeline_runs WHERE run_id=:run'),{'run':run}).scalar_one_or_none()
        if area is None or area['mode']!='live':raise ValueError('Real production requires a real-source analysis run')
        conn.execute(text('''INSERT INTO screening.pipeline_attempts(attempt_id,status,stage,study_area,run_id)
            VALUES (:attempt,'running',:stage,CAST(:area AS jsonb),:run)'''),
            {'attempt':attempt,'stage':stage,'area':json.dumps({**area,'production_window':{'start':start,'end':end}}),'run':run})
    try:
        snapshot=acquire_snapshot(source,cache or HttpCache(),refresh=refresh)
        stage='production:load-and-link'
        with engine.begin() as conn:
            conn.execute(text('UPDATE screening.pipeline_attempts SET stage=:stage WHERE attempt_id=:attempt'),
                         {'stage':stage,'attempt':attempt})
        report=import_csv(engine,run_id,snapshot.path,source,start=start,end=end,
                          retrieved_at=snapshot.metadata['retrieved_at'],acquisition=snapshot.metadata,**kwargs)
        with engine.begin() as conn:
            conn.execute(text("UPDATE screening.pipeline_attempts SET status='succeeded',stage='production:complete',finished_at=now() WHERE attempt_id=:attempt"),
                         {'attempt':attempt})
        return report
    except Exception as exc:
        with engine.begin() as conn:
            conn.execute(text('''UPDATE screening.pipeline_attempts SET status='failed',stage=:stage,finished_at=now(),
                error_code=:code,error_summary='Production refresh failed; no partial batch is activated. Inspect the active batch and source metadata.'
                WHERE attempt_id=:attempt'''),{'stage':stage,'code':type(exc).__name__,'attempt':attempt})
        raise


def load_demo_production(engine,run_id: str,*,start: str='2026-08',end: str='2026-10',**kwargs):
    source=Source(key='synthetic_production',kind='file',role='production',
        license_note='Project-authored synthetic fixture, not Petrinex data',reporting_level='mixed',
        attribution_values={'W':'well','F':'facility','U':'unknown'},
        well_identifier_field='source_well_id',identifier_namespace='synthetic-demo-well-id',
        join_evidence='Synthetic fixture IDs exactly match the synthetic well source IDs.',
        adjustment_activities=['ADJUSTMENT'],adjustment_note='Synthetic example of a documented signed adjustment.',
        field_mapping={'source_record_id':'ROW_ID','period':'MONTH','product':'PRODUCT','activity':'ACTIVITY','volume':'VOLUME',
                       'unit':'UNIT','attribution_level':'LEVEL','reporting_facility_id':'FACILITY','well_identifier_nullable':'WELL_ID'})
    return import_csv(engine,run_id,ROOT/'tests/fixtures/production_demo.csv',source,
                      start=start,end=end,synthetic=True,**kwargs)
