"""Alberta water acquisition adapted from the user-supplied hydrography importer.

Use the existing audited acquisition/contracts. Publish all selected layers
together; a failed refresh never exposes a mixture of old and new batches.
"""
import hashlib
import json
from collections import Counter
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import text

from src.artifacts import write_json
from src.config import ROOT, Source, SourceCatalog, load_source_catalog, load_study_area
from src.contracts.spatial import validate_records
from src.db.migrations import migrate
from src.db.workflow import serialized_workflow
from src.sources.arcgis import acquire_arcgis
from src.sources.files import acquire_file
from src.sources.http import HttpCache


def water_sources(catalog, include_optional=False):
    return [source for source in catalog.sources if source.role == 'analysis' and source.category == 'water'
            and (source.priority == 'core' or source.enabled or include_optional)]


def water_requirements(catalog, include_optional=False):
    sources = water_sources(catalog, include_optional)
    missing = []
    if not sources:
        missing.append('No water sources are configured.')
    for source in sources:
        if not source.verified or (not source.enabled and source.priority == 'core'):
            missing.append(f'{source.key}: source metadata and permission must be verified/enabled.')
        if not source.coverage_note:
            missing.append(f'{source.key}: a geographic/layer coverage note is required.')
    return missing


@serialized_workflow
def import_waterways(engine, *, catalog=None, area=None, include_optional=False, refresh=False,
                     max_records=10000, cache=None, raw_root=None, output_root=None, progress=lambda _: None):
    catalog = catalog if catalog is not None else load_source_catalog()
    area = area or load_study_area(ROOT / 'config/study_area.live.yml')
    if area.mode != 'live':
        raise ValueError('Water import requires a live study area, independently of synthetic demo results')
    missing = water_requirements(catalog, include_optional)
    if missing:
        raise ValueError('Water-source preflight: ' + '; '.join(missing))
    if not 1 <= max_records <= 100000:
        raise ValueError('Water record cap must be between 1 and 100,000 per source')
    sources = [Source.model_validate(source.model_dump() | {'enabled': True})
               for source in water_sources(catalog, include_optional)]
    cache = cache or HttpCache()
    migrate(engine)
    attempt, stage = uuid4(), 'water:preflight'
    with engine.begin() as conn:
        conn.execute(text('''INSERT INTO screening.pipeline_attempts(attempt_id,status,stage,study_area)
            VALUES (:id,'running',:stage,CAST(:area AS jsonb))'''),
            {'id': attempt, 'stage': stage, 'area': area.model_dump_json()})
    try:
        acquisitions, bundles, batches = {}, {}, {}
        for source in sorted(sources, key=lambda item: item.key):
            stage = f'water:acquire:{source.key}'
            progress(stage)
            with engine.begin() as conn:
                conn.execute(text('UPDATE screening.pipeline_attempts SET stage=:stage WHERE attempt_id=:id'),
                             {'stage': stage, 'id': attempt})
            adapter = acquire_arcgis if source.kind == 'arcgis' else acquire_file
            acquired = adapter(source, area, cache, refresh=refresh, max_records=max_records)
            acquisitions[source.key] = acquired
            bundles[source.key] = acquired.archive(raw_root or ROOT / 'data/raw/hydrography')
            batches[source.key] = validate_records(acquired.records, 'features', acquired.records_crs, area)
        identities = {key: bundle[2]['content_identity_sha256'] for key, bundle in bundles.items()}
        digest = hashlib.sha256(json.dumps({'area': area.model_dump(mode='json'), 'sources': identities,
                                          'contract_version': 1}, sort_keys=True).encode()).hexdigest()
        import_id = str(uuid5(NAMESPACE_URL, 'alberta-water-v1:' + digest))
        quarantines = [{**row, 'source_key': key, 'raw_payload_reference':
                       str(bundles[key][1]) + '#selected_records/' + row['record_reference'].split('/')[1]}
                       for key, batch in batches.items() for row in batch.rejected]
        gaps = [row for row in quarantines if row['reason_code'] != 'outside_study_area']
        report = {'import_id': import_id, 'study_area': area.model_dump(mode='json'),
                  'feature_count': sum(len(batch.accepted) for batch in batches.values()),
                  'quarantined_count': len(quarantines), 'coverage_status': 'incomplete' if gaps else 'complete',
                  'screening_run_published': False, 'environmental_margin_m': 500,
                  'source_identities': identities,
                  'sources': [{key: value for key, value in bundle[2].items() if key != 'selected_records'}
                              for bundle in bundles.values()],
                  'validation': {key: {'accepted': len(batch.accepted), 'rejected': len(batch.rejected),
                                      'reason_counts': dict(Counter(row['reason_code'] for row in batch.rejected))}
                                 for key, batch in batches.items()},
                  'quarantines': quarantines,
                  'coverage_note': 'Coverage applies only to configured feature codes, selected sources and study area plus 500 m; complete acquisition is not proof of positional accuracy.'}
        stage = 'water:load'
        progress(stage)
        with engine.begin() as conn:
            prior = conn.execute(text('SELECT import_id FROM screening.water_imports WHERE import_id=:id'),
                                 {'id': import_id}).scalar_one_or_none()
            if prior is None:
                conn.execute(text('''INSERT INTO screening.water_imports
                    (import_id,study_area,manifest,feature_count,quarantined_count,coverage_status)
                    VALUES (:id,CAST(:area AS jsonb),CAST(:manifest AS jsonb),:features,:rejects,:coverage)'''),
                    {'id': import_id, 'area': area.model_dump_json(), 'manifest': json.dumps(report),
                     'features': report['feature_count'], 'rejects': len(quarantines), 'coverage': report['coverage_status']})
                for key, batch in batches.items():
                    raw = {str(row.get('source_feature_id', '')).strip(): row for row in acquisitions[key].records}
                    for row in batch.accepted:
                        original = raw[row['source_feature_id']]
                        conn.execute(text('''INSERT INTO screening.water_features
                            (import_id,source_key,source_feature_id,name,feature_type_code,properties,geom)
                            VALUES (:id,:key,:source_feature_id,:name,:code,CAST(:properties AS jsonb),ST_GeomFromText(:geometry_wkt,3400))'''),
                            {'id': import_id, 'key': key, 'code': original.get('feature_type_code'),
                             'properties': json.dumps(original.get('_source_properties', {})), **row})
            count = conn.execute(text('SELECT count(*) FROM screening.water_features WHERE import_id=:id'),
                                 {'id': import_id}).scalar_one()
            if count != report['feature_count']:
                raise ValueError('Stored water feature counts do not match validated acquisition')
            stage = 'water:export'
            # Disk failure rolls back a new database inventory too.
            write_json((output_root or ROOT / 'outputs/waterways') / import_id / 'manifest.json', report)
        with engine.begin() as conn:
            conn.execute(text("UPDATE screening.pipeline_attempts SET status='succeeded',stage='water:complete',finished_at=now() WHERE attempt_id=:id"),
                         {'id': attempt})
        return report | {'reused': prior is not None}
    except Exception as exc:
        with engine.begin() as conn:
            conn.execute(text("""UPDATE screening.pipeline_attempts SET status='failed',stage=:stage,
                finished_at=now(),error_code=:code,error_summary='Water import failed; prior inventory and screening results retained.'
                WHERE attempt_id=:id"""), {'stage': stage, 'code': type(exc).__name__, 'id': attempt})
        raise


def latest_water_import(engine, import_id=None):
    with engine.connect() as conn:
        if not conn.execute(text("SELECT to_regclass('screening.water_imports')")).scalar_one():
            return None
        if import_id is not None:
            return conn.execute(text('SELECT manifest FROM screening.water_imports WHERE import_id=:id'),
                                {'id': import_id}).scalar_one_or_none()
        return conn.execute(text('SELECT manifest FROM screening.water_imports ORDER BY imported_at DESC,import_id DESC LIMIT 1')).scalar_one_or_none()


def water_features(engine, import_id):
    with engine.connect() as conn:
        rows = conn.execute(text('''SELECT source_key,source_feature_id,name,feature_type_code,
            ST_AsGeoJSON(ST_Transform(geom,4326)) AS geometry FROM screening.water_features
            WHERE import_id=:id ORDER BY source_key,source_feature_id'''), {'id': import_id}).mappings()
        return [{**dict(row), 'feature_type': 'water', 'geometry': json.loads(row['geometry'])} for row in rows]
