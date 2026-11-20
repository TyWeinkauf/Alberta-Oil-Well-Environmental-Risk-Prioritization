"""Stream full provincial hydrography inventories into PostGIS."""
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid4, uuid5

from psycopg.types.json import Jsonb
from sqlalchemy import text

from src.config import ROOT, Source, load_source_catalog
from src.contracts.spatial import validate_records
from src.db.migrations import migrate
from src.db.workflow import serialized_workflow
from src.sources.arcgis import open_arcgis_pages
from src.sources.http import HttpCache

BASE_SERVICE = 'https://geospatial.alberta.ca/titan/rest/services/environment/base_water_feature/MapServer'
BASE_QUERY = f'{BASE_SERVICE}/72/query'
UPDATE_QUERY = ('https://geospatial.alberta.ca/titan/rest/services/environment/'
                'inland_base_hydrography_update_10tm_nad83_aep/MapServer/9/query')
MAX_RECORDS = 2_000_000


@dataclass(frozen=True)
class ProvinceLayer:
    layer_id: int
    source_key: str
    name: str
    unit: str
    geometry_types: frozenset[str]
    attempt_prefix: str
    batch_size: int

    @property
    def scope(self) -> str:
        return f'alberta_layer_{self.layer_id}'


PROVINCE_WATERBODIES = ProvinceLayer(72, 'alberta_water_lakes_rivers', 'Lake/River (20K)', 'polygons',
                                    frozenset({'Polygon', 'MultiPolygon'}), 'waterbody', 200)
PROVINCE_STREAMS = ProvinceLayer(107, 'alberta_water_streams', 'Stream (20K)', 'stream lines',
                                 frozenset({'LineString', 'MultiLineString'}), 'streams', 500)
PROVINCE_SCOPE = PROVINCE_WATERBODIES.scope
PROVINCE_STREAM_SCOPE = PROVINCE_STREAMS.scope
PROVINCE_SCOPES = (PROVINCE_SCOPE, PROVINCE_STREAM_SCOPE)


def province_source(layer: ProvinceLayer = PROVINCE_WATERBODIES) -> Source:
    catalog = load_source_catalog(ROOT / 'config/source_catalog.yml')
    source = next(item for item in catalog.sources if item.key == layer.source_key)
    return Source.model_validate(source.model_dump() | {
        'arcgis_where': '1=1', 'arcgis_preserve_properties': True,
        'arcgis_batch_size': layer.batch_size,
        'coverage_note': f'Every published record in Alberta Base Water Feature layer {layer.layer_id}.',
    })


def import_province_waterbodies(engine, *, cache=None, source=None, max_records=MAX_RECORDS,
                               progress=lambda _: None):
    return import_province_layer(engine, PROVINCE_WATERBODIES, cache=cache, source=source,
                                 max_records=max_records, progress=progress)


def import_province_streams(engine, *, cache=None, source=None, max_records=MAX_RECORDS,
                           progress=lambda _: None):
    return import_province_layer(engine, PROVINCE_STREAMS, cache=cache, source=source,
                                 max_records=max_records, progress=progress)


@serialized_workflow
def import_province_layer(engine, layer: ProvinceLayer, *, cache, source, max_records, progress):
    source = source if source is not None else province_source(layer)
    if (source.kind != 'arcgis' or source.category != 'water' or source.layer_id != layer.layer_id
            or not source.enabled or not source.verified or source.arcgis_where != '1=1'
            or not source.arcgis_preserve_properties):
        raise ValueError(f'The Alberta inventory requires verified layer {layer.layer_id} with all records and properties enabled')
    if not 1 <= max_records <= MAX_RECORDS:
        raise ValueError(f'Provincial record guard must be between 1 and {MAX_RECORDS:,}')
    cache = cache if cache is not None else HttpCache(max_bytes=64 * 1024**2, max_total_bytes=16 * 1024**3)
    migrate(engine)
    attempt = uuid4()
    area = {'name': f'Alberta · {layer.name}', 'mode': 'live'}
    with engine.begin() as conn:
        conn.execute(text('''INSERT INTO screening.pipeline_attempts(attempt_id,status,stage,study_area)
            VALUES (:attempt,'running',:stage,CAST(:area AS jsonb))'''),
            {'attempt': attempt, 'stage': f'{layer.attempt_prefix}:acquire', 'area': json.dumps(area)})
    try:
        reader = open_arcgis_pages(source, None, cache, refresh=True, max_records=max_records)
        expected = reader.inspection['count']
        if expected == 0:
            raise ValueError(f'Province-wide layer {layer.layer_id} returned zero records')
        progress(f'Layer {layer.layer_id} reports {expected:,} {layer.unit}. Loading verified ID batches.')
        responses = [snapshot.metadata for snapshot in reader.responses]
        rejections = Counter()
        accepted = 0
        with engine.begin() as conn:
            conn.exec_driver_sql('''CREATE TEMP TABLE province_water_stage (
                feature_id text PRIMARY KEY, name text, code text, properties jsonb,
                wkt text, reason_code text, reason_detail text, rejected_payload jsonb
            ) ON COMMIT DROP''')
            with conn.connection.driver_connection.cursor() as cursor, cursor.copy('COPY province_water_stage FROM STDIN') as copy:
                for page_number, (snapshot, records) in enumerate(reader.pages, start=1):
                    responses.append(snapshot.metadata)
                    batch = validate_records(records, 'features', 'EPSG:4326', None)
                    by_id = {row['source_feature_id']: row for row in batch.accepted}
                    rejects = {int(row['record_reference'].split('/')[-1]): row for row in batch.rejected}
                    for index, record in enumerate(records):
                        feature_id = record['source_feature_id']
                        issue = rejects.get(index)
                        if issue is None and record['geometry']['type'] not in layer.geometry_types:
                            issue = {'reason_code': 'geometry_type',
                                     'reason_detail': f'Layer {layer.layer_id} requires {layer.unit}'}
                        if issue is None:
                            row = by_id[feature_id]
                            copy.write_row((feature_id, row['name'], record['feature_type_code'],
                                            Jsonb(record['_source_properties']), row['geometry_wkt'], None, None, None))
                            accepted += 1
                        else:
                            copy.write_row((feature_id, None, None, None, None, issue['reason_code'],
                                            issue['reason_detail'], Jsonb(record)))
                            rejections[issue['reason_code']] += 1
                    if page_number % 50 == 0:
                        progress(f'Validated {accepted + rejections.total():,} of {expected:,} records.')
            after = open_arcgis_pages(source, None, cache, refresh=True, max_records=max_records)
            if (reader.object_ids != after.object_ids
                    or reader.inspection['last_edit_date'] != after.inspection['last_edit_date']):
                raise ValueError(f'Layer {layer.layer_id} changed while pages were downloading. Repeat the import.')
            if accepted + rejections.total() != expected:
                raise ValueError(f'Layer {layer.layer_id} validation did not account for every published record')
            identity = {'source': source.model_dump(mode='json'), 'version': 1,
                        'hashes': [entry['checksum_sha256'] for entry in responses]}
            digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
            import_id = uuid5(NAMESPACE_URL, f'alberta-layer-{layer.layer_id}:{digest}')
            report = {
                'import_id': str(import_id), 'scope': layer.scope, 'study_area': area,
                'source_url': f'{str(source.url).rstrip("/")}/{layer.layer_id}', 'source_key': source.key,
                'license_note': source.license_note, 'native_crs': reader.native_crs,
                'analysis_crs': 'EPSG:3400', 'query': reader.inspection, 'source_responses': responses,
                'feature_count': accepted, 'quarantined_count': rejections.total(),
                'quarantine_reasons': dict(rejections),
                'coverage_status': 'incomplete' if rejections else 'complete',
            }
            reused = conn.execute(text('''INSERT INTO screening.water_imports
                (import_id,study_area,manifest,feature_count,quarantined_count,coverage_status)
                VALUES (:id,CAST(:area AS jsonb),CAST(:manifest AS jsonb),:accepted,:rejected,:coverage)
                ON CONFLICT (import_id) DO NOTHING RETURNING import_id'''),
                {'id': import_id, 'area': json.dumps(area), 'manifest': json.dumps(report),
                 'accepted': accepted, 'rejected': rejections.total(),
                 'coverage': report['coverage_status']}).scalar_one_or_none() is None
            if not reused:
                params = {'id': import_id, 'source': source.key}
                conn.execute(text('''INSERT INTO screening.water_features
                    (import_id,source_key,source_feature_id,name,feature_type_code,properties,geom)
                    SELECT :id,:source,feature_id,name,code,properties,ST_GeomFromText(wkt,3400)
                    FROM province_water_stage WHERE reason_code IS NULL'''), params)
                conn.execute(text('''INSERT INTO screening.water_feature_rejects
                    (import_id,source_key,source_feature_id,reason_code,reason_detail,payload)
                    SELECT :id,:source,feature_id,reason_code,reason_detail,rejected_payload
                    FROM province_water_stage WHERE reason_code IS NOT NULL'''), params)
                conn.exec_driver_sql('ANALYZE screening.water_features')
            counts = conn.execute(text('''SELECT
                (SELECT count(*) FROM screening.water_features WHERE import_id=:id),
                (SELECT count(*) FROM screening.water_feature_rejects WHERE import_id=:id)'''),
                {'id': import_id}).one()
            if tuple(counts) != (accepted, rejections.total()):
                raise ValueError('Stored provincial feature counts do not match the validated layer')
            conn.execute(text("""UPDATE screening.pipeline_attempts SET status='succeeded',
                stage=:stage,finished_at=now() WHERE attempt_id=:id"""),
                {'id': attempt, 'stage': f'{layer.attempt_prefix}:complete'})
        return report | {'reused': reused}
    except Exception as exc:
        with engine.begin() as conn:
            conn.execute(text("""UPDATE screening.pipeline_attempts SET status='failed',finished_at=now(),
                error_code=:code,error_summary='Provincial hydrography import failed. Prior inventories are available.'
                WHERE attempt_id=:id"""), {'id': attempt, 'code': type(exc).__name__})
        raise
