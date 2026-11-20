"""Metre-based classroom geometry and proximity using the shared classifier."""
import hashlib
import random
from collections import defaultdict
from itertools import cycle

from shapely import transform
from shapely.affinity import rotate, translate
from shapely.geometry import LineString, Point, mapping, shape
from shapely.geometry.base import BaseGeometry

from src.contracts.spatial import CATEGORIES
from src.demo.regions import project_from
from src.spatial.classification import THRESHOLDS, classify_distance
from src.spatial.extent import projected_bbox

ANALYSIS_CRS = 'EPSG:3400'
SEARCH_MARGIN_M = max(THRESHOLDS)
GENERATOR_VERSION = 1
FEATURE_PROVENANCE = 'synthetic_environment'
FEATURE_SPECS = (
    ('water', 'stream', 35, None),
    ('water', 'waterbody', 215, 105),
    ('wetland', 'wetland', 80, 115),
    ('protected_area', 'protected_area', 195, 210),
    ('critical_habitat', 'critical_habitat', 335, 120),
    ('esa', 'significance_area', 0, 140),
)


def projected_wells(wells: list[dict], source_crs: str) -> dict[int, Point]:
    transformer = project_from(source_crs, ANALYSIS_CRS)
    points = {}
    for row in wells:
        raw = row['raw']
        coordinates = transformer.transform(
            float(raw['SH_Actual_Longitude']), float(raw['SH_Actual_Latitude']), errcheck=True)
        points[row['source_row']] = Point(coordinates)
    return points


def region_seed(seed: int, region_id: str) -> int:
    tag = f'{GENERATOR_VERSION}:{seed}:{region_id}'
    return int.from_bytes(hashlib.sha256(tag.encode()).digest()[:8])


def generate_features(region_id: str, bbox: tuple[float, float, float, float],
                      seed: int, points: dict[int, Point]) -> list[dict]:
    rng = random.Random(seed)
    anchors = cycle(rng.sample(list(points.values()), min(len(points), len(FEATURE_SPECS))))
    margin = projected_bbox(bbox).buffer(SEARCH_MARGIN_M)
    features = []
    for category, subtype, offset, radius in FEATURE_SPECS:
        anchor = next(anchors)
        if radius is None:
            template = LineString([(-260, offset + 45), (0, offset), (205, offset + 60), (420, offset + 15)])
        else:
            center = offset + radius if offset else 0
            template = Point(center, 0).buffer(radius, quad_segs=8)
        geometry = margin.intersection(translate(rotate(template, rng.randrange(360), origin=(0, 0)),
                                                 xoff=anchor.x, yoff=anchor.y))
        feature_id = f'{region_id}-{subtype}'
        features.append({
            'source_feature_id': feature_id, 'feature_type': category, 'subtype': subtype,
            'name': f'Synthetic {subtype.replace("_", " ")}',
            'provenance': FEATURE_PROVENANCE, 'geometry_3400': mapping(geometry),
        })
    return features


def feature_geometry(feature: dict) -> BaseGeometry:
    geometry = shape(feature['geometry_3400'])
    if geometry.is_empty or not geometry.is_valid or geometry.geom_type not in {
        'LineString', 'MultiLineString', 'Polygon', 'MultiPolygon',
    }:
        raise ValueError('Classroom features require valid, nonempty line or polygon geometry')
    return geometry


def analyze(wells: list[dict], points: dict[int, Point], features: list[dict],
            coverage: dict[str, str]) -> list[dict]:
    by_category = defaultdict(list)
    for feature in features:
        by_category[feature['feature_type']].append(
            (feature['source_feature_id'], feature_geometry(feature)))
    rows = []
    for well in wells:
        key = well['source_row']
        for category in sorted(CATEGORIES):
            distance, feature_id = min(
                ((points[key].distance(geometry), identifier) for identifier, geometry in by_category[category]),
                default=(float('inf'), None),
            )
            if distance > SEARCH_MARGIN_M:
                distance, feature_id = None, None
            status = coverage.get(category, 'unavailable')
            result = status if status != 'complete' else ('matched' if feature_id else 'no_feature_within_500m')
            rows.append({
                'well_pk': key, 'source_well_id': well['raw']['Well_Licence_Number'],
                'category': category, 'nearest_feature_id': feature_id, 'distance_m': distance,
                'coverage_status': status, 'result_state': result, **classify_distance(distance),
            })
    return rows


def display_geometry(geometry: BaseGeometry) -> dict:
    transformer = project_from(ANALYSIS_CRS, 4326)
    return mapping(transform(geometry, transformer.transform, interleaved=False))


def selected_buffer(well: dict, threshold: int) -> dict:
    return display_geometry(Point(well['analysis_x'], well['analysis_y']).buffer(threshold))
