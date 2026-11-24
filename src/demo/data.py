"""Build and load a checksummed, portable classroom package."""
import hashlib
import json
from datetime import date
from pathlib import Path

from src.artifacts import atomic_output
from src.config import ROOT
from src.contracts.spatial import CATEGORIES
from src.demo.regions import (
    REGION_IDS, SELECTION_METHOD, DemoRegions, coordinate_reference, project_from, sample_inventory,
)
from src.demo.spatial import (
    ANALYSIS_CRS, FEATURE_PROVENANCE, FEATURE_SPECS, GENERATOR_VERSION, SEARCH_MARGIN_M, WATER_PROVENANCE,
    analyze, display_geometry, feature_geometry, generate_features, imported_water_extent, projected_wells, region_seed,
)
from src.sources.st37 import FIELDS, row_errors
from src.spatial.classification import THRESHOLDS
from src.spatial.extent import projected_bbox

SYNTHETIC_PACKAGE = ROOT / 'data/demo/classroom/demo.json'
DEFAULT_PACKAGE = SYNTHETIC_PACKAGE.with_name('demo_imported_water.json')
PACKAGE_VERSION = 1
MAX_PACKAGE_BYTES = 512 * 1024
DATASET_MODE = 'illustrative_classroom'
IMPORTED_WATER_MODE = 'classroom_imported_water'
MIXED_PROVENANCE = 'imported_water_and_synthetic_other_layers'
IMPORTED_WATER_NOTICE = (
    'Classroom demo: real AER ST37 wells and imported Alberta waterbodies and streams. '
    'Water distances are measured from the imported geometries. Wetlands, protected areas, habitat '
    'and significance areas are synthetic, and distances to those layers are simulated. '
    'This is educational proximity screening.'
)
WELL_PROVENANCE = 'actual_aer_st37_surface_hole'
NOTICE = (
    'Illustrative classroom demo: real AER ST37 well locations with synthetic environmental features. '
    'Distances and proximity bands describe the simulated features only. '
    'They do not describe actual environmental conditions, contamination, legal setbacks or the risk of these real wells.'
)
PREVIEW_NOTICE = (
    'ST37 classroom preview: real AER ST37 well records with source coordinates shown as reported. '
    'The workbook coordinate datum is pending. Map geometry and simulated distances require a verified datum.'
)
AER_PAGE = 'https://www.aer.ca/data-and-performance-reports/statistical-reports/st37'
AER_TERMS = 'https://www.aer.ca/copyright-and-disclaimer'
SOURCE_CREDIT = 'Source: Alberta Energy Regulator, ST37 List of Wells in Alberta (surface holes).'


def json_bytes(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def read_package_bytes(path: Path) -> bytes:
    with path.open('rb') as handle:
        contents = handle.read(MAX_PACKAGE_BYTES + 1)
    if len(contents) > MAX_PACKAGE_BYTES:
        raise ValueError('Classroom package exceeds its file size limit')
    return contents


def decode_package(contents: bytes) -> dict:
    if len(contents) > MAX_PACKAGE_BYTES:
        raise ValueError('Classroom package exceeds its file size limit')
    try:
        package = json.loads(contents)
        manifest = package['manifest']
        regions = package['regions']
        expected = hashlib.sha256(json_bytes({'manifest': manifest, 'regions': regions})).hexdigest()
        if package['package_id'] != expected:
            raise ValueError('Classroom package checksum mismatch')
        if manifest['version'] != PACKAGE_VERSION or manifest['mode'] not in (DATASET_MODE, IMPORTED_WATER_MODE):
            raise ValueError('Unsupported classroom package version or mode')
        coordinate = manifest['coordinate_reference']
        real_water = manifest['mode'] == IMPORTED_WATER_MODE
        water_sources = {}
        if real_water:
            declared = manifest['water_sources']
            water_sources = {source['import_id']: source for source in declared}
            if (not coordinate or len(water_sources) != 2 or len(declared) != 2
                    or {source['kind'] for source in declared} != {'waterbody', 'stream'}
                    or any(source['coverage_status'] not in {'complete', 'incomplete'} for source in declared)
                    or manifest['environment_provenance'] != MIXED_PROVENANCE):
                raise ValueError('Real-water classroom packages require both water inventories and a verified well CRS')
        if coordinate is not None and coordinate_reference(coordinate['crs'], coordinate['evidence']) != coordinate:
            raise ValueError('Invalid coordinate evidence in classroom package')
        notice = IMPORTED_WATER_NOTICE if real_water else (NOTICE if coordinate else PREVIEW_NOTICE)
        if (manifest['disclaimer'] != notice
                or manifest['readiness'] != ('projected' if coordinate else 'awaiting_workbook_datum')):
            raise ValueError('Classroom package readiness and disclaimer must agree with coordinate evidence')
        config = DemoRegions.model_validate(manifest['config'])
        if set(regions) != set(REGION_IDS):
            raise ValueError('Classroom package must contain both regions')
        well_keys, licence_ids = set(), set()
        for key in REGION_IDS:
            group = regions[key]
            wells = group['wells']
            if (not isinstance(group['candidate_count'], int) or group['candidate_count'] < 1 or
                    len(wells) != min(config.sample_limit, group['candidate_count'])):
                raise ValueError('Regional classroom sample count does not match the manifest')
            for well in wells:
                index, raw = well['source_row'], well['raw']
                licence = raw['Well_Licence_Number']
                if (not isinstance(index, int) or index < 2 or index in well_keys or licence in licence_ids
                        or not isinstance(well['quality_warnings'], str)
                        or set(raw) != set(FIELDS) or not all(isinstance(value, str) for value in raw.values())
                        or row_errors(raw)):
                    raise ValueError('Invalid or duplicate well in classroom package')
                well_keys.add(index)
                licence_ids.add(licence)
            features = group['features']
            if coordinate:
                expected_types = {(category, subtype) for category, subtype, _, _ in FEATURE_SPECS
                                  if not real_water or category != 'water'}
                synthetic = [f for f in features if not real_water or f['feature_type'] != 'water']
                if len(synthetic) != len(expected_types) or {
                    (feature['feature_type'], feature['subtype']) for feature in synthetic
                } != expected_types:
                    raise ValueError('Classroom package has incomplete synthetic scenarios')
                margin = projected_bbox(config.regions[key].bbox_wgs84).buffer(SEARCH_MARGIN_M + 1e-6)
                for feature in synthetic:
                    if (feature['source_feature_id'] != f'{key}-{feature["subtype"]}'
                            or feature['provenance'] != FEATURE_PROVENANCE
                            or not margin.covers(feature_geometry(feature))):
                        raise ValueError('Invalid synthetic feature provenance, ID or regional margin')
                if real_water:
                    validate_imported_features(features, water_sources, config.regions[key].bbox_wgs84)
            elif features or group['generator_seed'] is not None:
                raise ValueError('A pending-datum package may only contain unprojected well records')
    except (KeyError, TypeError, AttributeError, IndexError) as exc:
        raise ValueError('Invalid classroom package structure') from exc
    return package


def validate_imported_features(features: list[dict], sources: dict,
                               bbox: tuple[float, float, float, float]):
    extent = imported_water_extent(bbox).buffer(1e-6)
    seen = set()
    for feature in features:
        if feature['feature_type'] != 'water':
            continue
        source = sources.get(feature.get('import_id'))
        identifier = feature['source_feature_id']
        publisher_id = feature['publisher_feature_id']
        geometry = feature_geometry(feature)
        geometry_kind = 'stream' if geometry.geom_type.endswith('LineString') else 'waterbody'
        if (feature['provenance'] != WATER_PROVENANCE or not source or source['kind'] != geometry_kind
                or feature['subtype'] != geometry_kind or not publisher_id or identifier != f'{source["layer"]}:{publisher_id}'
                or identifier in seen or not extent.covers(geometry)):
            raise ValueError('Invalid imported water feature, provenance or regional extent')
        seen.add(identifier)


def prepare_package(report_path: Path, config: DemoRegions, output: Path, *,
                    coordinate_crs: str | None = None, crs_evidence: str | None = None,
                    release_date: date | None = None,
                    hydrography: tuple[list[dict], dict[str, list[dict]]] | None = None) -> dict:
    """Read the retained inventory snapshot. Publish the new package in one replacement."""
    report_path, output = report_path.resolve(), output.resolve()
    if output.suffix.lower() != '.json' or output == report_path:
        raise ValueError('Choose a separate .json classroom output path')
    if output.exists():
        decode_package(read_package_bytes(output))
    coordinate = coordinate_reference(coordinate_crs, crs_evidence)
    if hydrography is not None and not coordinate:
        raise ValueError('Imported water requires verified well coordinates')
    report_bytes = report_path.read_bytes()
    report = json.loads(report_bytes)
    source = report['source']
    inventory_hash = report['artifacts']['inventory']['sha256']
    regions = sample_inventory(report_path.with_name('inventory.csv'), inventory_hash,
                               report['source_rows'], report['accepted_rows'], config, coordinate)
    for key in REGION_IDS:
        group = regions[key]
        seed = region_seed(config.sample_seed, key)
        group['generator_seed'] = seed if coordinate else None
        group['features'] = (
            generate_features(key, config.regions[key].bbox_wgs84, seed,
                              projected_wells(group['wells'], coordinate['crs'])) if coordinate else []
        )
        if hydrography is not None:
            group['features'] = [f for f in group['features'] if f['feature_type'] != 'water'] + hydrography[1][key]
    manifest = {
        'version': PACKAGE_VERSION, 'mode': DATASET_MODE,
        'readiness': 'projected' if coordinate else 'awaiting_workbook_datum',
        'config': config.model_dump(mode='json'),
        'coordinate_reference': coordinate,
        'selection_method': SELECTION_METHOD,
        'source': {
            'publisher': 'Alberta Energy Regulator', 'credit': SOURCE_CREDIT,
            'product_url': AER_PAGE, 'terms_url': AER_TERMS, 'worksheet': source['worksheet'],
            'workbook_sha256': source['sha256'], 'inventory_sha256': inventory_hash,
            'inventory_report_sha256': hashlib.sha256(report_bytes).hexdigest(),
            'inventory_identity': report['identity'], 'inventory_wells': report['accepted_rows'],
            'release_date': release_date.isoformat() if release_date else source.get('release_date'),
            'downloaded_at': source.get('downloaded_at'),
            'provenance': WELL_PROVENANCE,
        },
        'generator_version': GENERATOR_VERSION,
        'environment_provenance': FEATURE_PROVENANCE,
        'analysis_crs': ANALYSIS_CRS, 'thresholds_m': THRESHOLDS, 'search_margin_m': SEARCH_MARGIN_M,
        'disclaimer': NOTICE if coordinate else PREVIEW_NOTICE,
    }
    if hydrography is not None:
        manifest.update(mode=IMPORTED_WATER_MODE, water_sources=hydrography[0],
                        environment_provenance=MIXED_PROVENANCE, disclaimer=IMPORTED_WATER_NOTICE)
    payload = {'manifest': manifest, 'regions': regions}
    package = {'package_id': hashlib.sha256(json_bytes(payload)).hexdigest(), **payload}
    contents = json_bytes(package) + b'\n'
    decode_package(contents)
    with atomic_output(output) as candidate:
        candidate.write_bytes(contents)
    return package


def dashboard_for(package: dict, region_ids: tuple[str, ...]) -> dict:
    manifest = package['manifest']
    coordinate = manifest['coordinate_reference']
    to_display = project_from(coordinate['crs'], 4326) if coordinate else None
    dashboard: dict = {
        'run_id': package['package_id'], 'manifest': manifest,
        'candidate_count': 0, 'wells': [], 'features': [], 'proximity': [],
    }
    coverage = dict.fromkeys(CATEGORIES, 'complete') if coordinate else {}
    if any(source['coverage_status'] == 'incomplete' for source in manifest.get('water_sources', [])):
        coverage['water'] = 'incomplete'
    for key in region_ids:
        group = package['regions'][key]
        dashboard['candidate_count'] += group['candidate_count']
        points = projected_wells(group['wells'], coordinate['crs']) if coordinate else {}
        for row in group['wells']:
            raw = row['raw']
            source_longitude, source_latitude = raw['SH_Actual_Longitude'], raw['SH_Actual_Latitude']
            longitude, latitude = (
                to_display.transform(float(source_longitude), float(source_latitude), errcheck=True)
                if to_display else (None, None)
            )
            point = points.get(row['source_row'])
            dashboard['wells'].append({
                'well_pk': row['source_row'], 'region': manifest['config']['regions'][key]['name'],
                'source_well_id': raw['Well_Licence_Number'], 'licensee_name': raw['Licensee'],
                'lsd_text': raw['Licence_Surface_Location_Label'], 'status': raw['Licence_Status'],
                'operator_name_if_verified': None, 'uwi_if_available': None,
                'longitude': longitude, 'latitude': latitude,
                'source_longitude': source_longitude, 'source_latitude': source_latitude,
                'source_crs': coordinate['crs'] if coordinate else None,
                'analysis_x': point.x if point else None, 'analysis_y': point.y if point else None,
                'source_credit': SOURCE_CREDIT, 'well_provenance': WELL_PROVENANCE,
                'environment_provenance': manifest['environment_provenance'] if coordinate else 'not_generated',
                'mode': manifest['mode'], 'disclaimer': manifest['disclaimer'],
                'raw': raw, 'quality_warnings': row['quality_warnings'],
            })
        for feature in group['features']:
            dashboard['features'].append({
                'source_feature_id': feature['source_feature_id'], 'feature_type': feature['feature_type'],
                'name': feature['name'], 'provenance': FEATURE_PROVENANCE,
                'geometry': display_geometry(feature_geometry(feature)),
            })
        dashboard['proximity'].extend(analyze(group['wells'], points, group['features'], coverage))
    return dashboard
