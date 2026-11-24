"""Prepare a portable classroom extract from existing Alberta water imports."""
import json
from uuid import UUID

from sqlalchemy import Engine, text

from src.db.waterbodies import STREAM_COMPARISON_CODES
from src.demo.regions import REGION_IDS, DemoRegions
from src.demo.spatial import WATER_PROVENANCE, imported_water_extent
from src.sources.waterbodies import PROVINCE_SCOPE, PROVINCE_STREAM_SCOPE


def extract_imported_water(engine: Engine, config: DemoRegions, waterbodies_id: UUID,
                           streams_id: UUID) -> tuple[list[dict], dict[str, list[dict]]]:
    """Read and clip accepted polygons and stream lines for the two regions."""
    sources = []
    features: dict[str, list[dict]] = {key: [] for key in REGION_IDS}
    with engine.connect() as conn:
        for import_id, scope, kind, geometry_dimension, codes in (
            (waterbodies_id, PROVINCE_SCOPE, 'waterbody', 3, None),
            (streams_id, PROVINCE_STREAM_SCOPE, 'stream', 2, list(STREAM_COMPARISON_CODES)),
        ):
            row = conn.execute(text('''SELECT coverage_status, quarantined_count,
                manifest->>'source_url' AS source_url, manifest->>'source_key' AS source_key
                FROM screening.water_imports
                WHERE import_id=:id AND manifest->>'scope'=:scope AND feature_count>0'''),
                {'id': import_id, 'scope': scope}).mappings().one_or_none()
            if row is None:
                raise ValueError(f'Choose an accepted {kind} inventory for {scope}')
            source_id = str(import_id)
            sources.append({'import_id': source_id, 'layer': scope, 'kind': kind, **row,
                            'feature_codes': codes})
            for region in REGION_IDS:
                extent = imported_water_extent(config.regions[region].bbox_wgs84)
                result = conn.execute(text('''WITH region AS (
                    SELECT ST_GeomFromText(:extent, 3400) AS geom
                ), clipped AS (
                    SELECT w.source_feature_id, w.name, w.feature_type_code,
                        ST_CollectionExtract(ST_Intersection(w.geom,r.geom),:dimension) AS geometry
                    FROM screening.water_features w CROSS JOIN region r
                    WHERE w.import_id=:id AND w.source_key=:source AND ST_Intersects(w.geom,r.geom)
                        AND (CAST(:codes AS text[]) IS NULL OR w.feature_type_code=ANY(CAST(:codes AS text[])))
                ) SELECT source_feature_id, name, feature_type_code, ST_AsGeoJSON(geometry, 12, 0) AS geometry
                FROM clipped WHERE NOT ST_IsEmpty(geometry) ORDER BY source_feature_id COLLATE "C"'''),
                    {'id': import_id, 'source': row['source_key'], 'extent': extent.wkt,
                     'dimension': geometry_dimension, 'codes': codes}).mappings()
                for feature in result:
                    identifier = feature['source_feature_id']
                    features[region].append({
                        'source_feature_id': f'{scope}:{identifier}', 'publisher_feature_id': identifier,
                        'import_id': source_id, 'feature_type': 'water', 'subtype': kind,
                        'feature_type_code': feature['feature_type_code'],
                        'name': feature['name'] or f'Alberta {kind} {identifier}',
                        'provenance': WATER_PROVENANCE, 'geometry_3400': json.loads(feature['geometry']),
                    })
    return sources, features
