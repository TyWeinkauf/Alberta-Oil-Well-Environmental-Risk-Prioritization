"""All-source acquisition and an atomic PostGIS load/analyze transaction."""
import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import text

from src.artifacts import write_json
from src.config import ROOT, SourceCatalog, StudyArea, load_source_catalog, load_study_area
from src.contracts.spatial import CATEGORIES, validate_records
from src.db.migrations import migrate
from src.sources.arcgis import acquire_arcgis
from src.sources.files import acquire_file
from src.sources.http import HttpCache
from src.spatial.engine import Coverage, calculate_proximity


def live_requirements(catalog: SourceCatalog) -> list[str]:
    requirements=[]
    analytical=[s for s in catalog.sources if s.role=='analysis']
    for source in analytical:
        if source.priority=='core' and (not source.enabled or not source.verified):
            requirements.append(f'{source.key}: source location, licence, CRS and field mapping must be verified/enabled')
        if source.enabled and not source.coverage_note:
            requirements.append(f'{source.key}: verified geographic/layer coverage note is required')
    wells=[s for s in analytical if s.key=='aer_wells' and s.enabled and s.verified]
    categories={s.category for s in analytical if s.enabled and s.verified}
    if not wells:
        requirements.append('Core AER well source is not ready')
    if not {'water','protected_area','critical_habitat'}<=categories:
        requirements.append('Core water, protected-area and critical-habitat sources are not all ready')
    return requirements


def run_live(engine, *, catalog: SourceCatalog | None=None, area: StudyArea | None=None,
             cache: HttpCache | None=None, refresh: bool=False, max_records: int=10000,
             raw_root: Path | None=None, output_root: Path | None=None, progress=lambda _:None) -> dict:
    catalog=catalog or load_source_catalog()
    area=area or load_study_area(ROOT/'config/study_area.live.yml')
    if area.mode!='live':
        raise ValueError('Live ingestion requires study-area mode: live')
    requirements=live_requirements(catalog)
    if requirements:
        raise ValueError('Live source preflight is blocked: '+'; '.join(requirements))
    if not 1<=max_records<=100000:
        raise ValueError('Record cap must be between 1 and 100,000 per source')
    cache=cache or HttpCache()
    # Reserve headroom for response blobs, selected bundles, PostGIS and WAL.
    if shutil.disk_usage(ROOT).free < max(3*cache.max_bytes,4*cache.max_total_bytes):
        raise ValueError('Insufficient free disk for bounded downloads and source caches')
    migrate(engine)
    attempt_id=uuid4()
    with engine.begin() as conn:
        conn.execute(text('''INSERT INTO screening.pipeline_attempts (attempt_id,status,stage,study_area)
            VALUES (:attempt,'running','preflight',CAST(:area AS jsonb))'''),
                     {'attempt':attempt_id,'area':area.model_dump_json()})
    stage='preflight'
    try:
        acquisitions=[];batches={};bundles={}
        for source in sorted((s for s in catalog.sources if s.enabled and s.role=='analysis'),key=lambda s:s.key):
            stage=f'acquire:{source.key}';progress(stage)
            with engine.begin() as conn:
                conn.execute(text('UPDATE screening.pipeline_attempts SET stage=:stage WHERE attempt_id=:attempt'),
                             {'stage':stage,'attempt':attempt_id})
            adapter=acquire_arcgis if source.kind=='arcgis' else acquire_file
            acquisition=adapter(source,area,cache,refresh=refresh,max_records=max_records)
            entity='features' if source.category else 'wells'
            batches[source.key]=validate_records(acquisition.records,entity,acquisition.records_crs,area)
            bundles[source.key]=acquisition.archive(raw_root)
            acquisitions.append(acquisition)
        well_count=sum(len(batches[a.source.key].accepted) for a in acquisitions if not a.source.category)
        if not well_count:
            raise ValueError('Study area has no accepted well records; choose a supported pilot region')
        identities={a.source.key:bundles[a.source.key][2]['content_identity_sha256'] for a in acquisitions}
        config={'study_area':area.model_dump(mode='json'),'source_inputs':identities,'contract_version':1}
        digest=hashlib.sha256(json.dumps(config,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        run_id=uuid5(NAMESPACE_URL,'alberta-screening-live-v1:'+digest)
        coverage={}
        for category in CATEGORIES:
            relevant=[a for a in acquisitions if a.source.category==category]
            gaps=[r for a in relevant for r in batches[a.source.key].rejected if r['reason_code']!='outside_study_area']
            coverage[category]=Coverage(status='unavailable' if not relevant else 'incomplete' if gaps else 'complete',
                note='No enabled source for this category.' if not relevant else
                     'At least one feature was quarantined; dataset coverage is incomplete.' if gaps else
                     ' | '.join(a.source.coverage_note for a in relevant))
        stage='load-and-analyze';progress(stage)
        with engine.begin() as conn:
            conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('alberta-live:' || CAST(:run AS text)))"),{'run':run_id})
            existing=conn.execute(text('SELECT status FROM screening.pipeline_runs WHERE run_id=:run FOR UPDATE'),
                                  {'run':run_id}).scalar_one_or_none()
            if existing is None:
                conn.execute(text('''INSERT INTO screening.pipeline_runs(run_id,status,study_area,config_hash)
                    VALUES (:run,'loading',CAST(:area AS jsonb),:hash)'''),
                             {'run':run_id,'area':area.model_dump_json(),'hash':digest})
                for acquisition in acquisitions:
                    source=acquisition.source;batch=batches[source.key]
                    snapshot_id=uuid5(run_id,source.key)
                    checksum,path,bundle=bundles[source.key]
                    conn.execute(text('''INSERT INTO screening.source_snapshots
                        (snapshot_id,run_id,source_key,url,retrieved_at,checksum,license_note,native_crs,record_count)
                        VALUES (:snapshot,:run,:key,:url,:retrieved,:sha,:licence,:crs,:count)'''),
                        {'snapshot':snapshot_id,'run':run_id,'key':source.key,'url':str(source.url or source.metadata_url or ''),
                         'retrieved':max(datetime.fromisoformat(s.metadata['retrieved_at']) for s in acquisition.responses),
                         'sha':checksum,'licence':source.license_note,'crs':acquisition.native_crs,'count':len(acquisition.records)})
                    for row in batch.accepted:
                        if source.category:
                            conn.execute(text('''INSERT INTO screening.environmental_features
                                (snapshot_id,source_key,source_feature_id,feature_type,name,geom)
                                VALUES (:snapshot,:key,:source_feature_id,:feature_type,:name,ST_GeomFromText(:geometry_wkt,3400))'''),
                                         {'snapshot':snapshot_id,'key':source.key,**row})
                        else:
                            conn.execute(text('''INSERT INTO screening.wells
                                (snapshot_id,source_well_id,licensee_name,licensee_search,uwi_if_available,
                                 operator_name_if_verified,lsd_text,status,geom)
                                VALUES (:snapshot,:source_well_id,:licensee_name,:licensee_search,:uwi_if_available,
                                 :operator_name_if_verified,:lsd_text,:status,ST_GeomFromText(:geometry_wkt,3400))'''),
                                         {'snapshot':snapshot_id,**row})
                    for row in batch.rejected:
                        conn.execute(text('''INSERT INTO screening.quarantine_records
                            (run_id,source_key,record_reference,reason_code,reason_detail,raw_payload_reference)
                            VALUES (:run,:key,:record_reference,:reason_code,:reason_detail,:raw)'''),
                                     {'run':run_id,'key':source.key,'raw':str(path)+'#selected_records/'+row['record_reference'].split('/')[1],**row})
                conn.execute(text("UPDATE screening.pipeline_runs SET status='seeded' WHERE run_id=:run"),{'run':run_id})
            elif existing!='succeeded':
                raise ValueError('Existing live input identity has an incompatible run status')
            rows=calculate_proximity(conn,str(run_id),coverage)
            if len(rows)!=well_count*5:
                raise ValueError('Stored live well counts differ from validated source inputs')
            report={'run_id':str(run_id),'status':'succeeded','mode':'live','study_area':area.model_dump(mode='json'),
                    'config_hash':digest,'source_identities':identities,
                    'sources':[{k:v for k,v in bundles[a.source.key][2].items() if k!='selected_records'} for a in acquisitions],
                    'counts':{'wells':well_count,'features':sum(len(batches[a.source.key].accepted) for a in acquisitions if a.source.category),
                              'quarantined':sum(len(b.rejected) for b in batches.values()),'proximity_rows':len(rows)},
                    'coverage':{key:value.model_dump() for key,value in coverage.items()},
                    'validation':{key:{'accepted':len(batch.accepted),'rejected':len(batch.rejected),
                                       'reason_counts':dict(Counter(row['reason_code'] for row in batch.rejected))}
                                  for key,batch in batches.items()},
                    'transform_note':'Features clipped to projected study polygon plus 500 m; exact tangent intersections retain original valid geometry.',
                    'disclaimer':'Educational proximity screening, not an operational environmental risk assessment.'}
            stage='export-manifest';progress(stage)
            write_json((output_root or ROOT/'outputs/runs')/str(run_id)/'manifest.json',report)
            conn.execute(text("UPDATE screening.pipeline_runs SET status='succeeded',finished_at=coalesce(finished_at,now()) WHERE run_id=:run"),{'run':run_id})
        with engine.begin() as conn:
            conn.execute(text("""UPDATE screening.pipeline_attempts SET status='succeeded',stage='complete',
                finished_at=now(),run_id=:run WHERE attempt_id=:attempt"""),{'run':run_id,'attempt':attempt_id})
        return report
    except Exception as exc:
        with engine.begin() as conn:
            conn.execute(text('''UPDATE screening.pipeline_attempts SET status='failed',stage=:stage,finished_at=now(),
                error_code=:code,error_summary='Acquisition/validation/load failed; no partial dataset was published.'
                WHERE attempt_id=:attempt'''),{'stage':stage,'code':type(exc).__name__,'attempt':attempt_id})
        raise
