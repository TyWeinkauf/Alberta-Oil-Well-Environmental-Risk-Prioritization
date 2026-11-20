"""Probe up to ten records from a specified Alberta hydrography API."""
import argparse
import json
from pathlib import Path

from _bootstrap import run_cli
from src.artifacts import write_json
from src.config import ROOT
from src.sources.http import HttpCache
from src.sources.arcgis import open_arcgis_pages
from src.sources.waterbodies import BASE_QUERY, BASE_SERVICE, MAX_RECORDS, PROVINCE_STREAMS, UPDATE_QUERY, province_source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layer', choices=('update', 'base', 'streams'), default='update')
    check = parser.add_mutually_exclusive_group()
    check.add_argument('--count-only', action='store_true')
    check.add_argument('--verify-paging', action='store_true',
                       help='Check the count, full ID list and first batch of ten on a base layer')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.verify_paging:
        if args.layer == 'update':
            parser.error('--verify-paging applies to --layer base or --layer streams')
        source = (province_source(PROVINCE_STREAMS) if args.layer == 'streams' else province_source())
        source = source.model_copy(update={'arcgis_batch_size': 10})
        reader = open_arcgis_pages(source, None, HttpCache(max_bytes=32 * 1024**2),
                                   refresh=True, max_records=MAX_RECORDS)
        _, rows = next(reader.pages)
        print(f'Layer {source.layer_id} verified {reader.inspection["count"]:,} IDs and '
              f'{len(rows)} matching records in the first batch')
        return
    url = {'update': UPDATE_QUERY, 'base': BASE_QUERY, 'streams': f'{BASE_SERVICE}/107/query'}[args.layer]
    params = ({'where': '1=1', 'returnCountOnly': 'true', 'f': 'json'} if args.count_only else {
        'where': '1=1', 'outFields': '*', 'returnGeometry': 'true', 'outSR': 4326,
        'resultRecordCount': 10, 'f': 'geojson',
    })
    print(f'Querying Alberta waterbody layer: {args.layer}', flush=True)
    result = HttpCache(max_bytes=32 * 1024**2).get(url, params, refresh=True).json()
    if not isinstance(result, dict) or 'error' in result:
        raise ValueError(f'ArcGIS rejected the request: {result}')
    if args.count_only:
        count = result.get('count')
        if type(count) is not int or count < 0:
            raise ValueError('ArcGIS did not return a valid count')
        print(f'{count:,} records reported')
        return
    features = result.get('features')
    if result.get('type') != 'FeatureCollection' or not isinstance(features, list) or not 1 <= len(features) <= 10:
        raise ValueError('Expected a nonempty GeoJSON FeatureCollection of up to ten features')
    types = PROVINCE_STREAMS.geometry_types if args.layer == 'streams' else {'Polygon', 'MultiPolygon'}
    if not all(isinstance(feature, dict) and (feature.get('geometry') or {}).get('type') in types
               for feature in features):
        raise ValueError('Unexpected geometry type in the hydrography sample')
    default_name = 'streams_test.geojson' if args.layer == 'streams' else 'waterbodies_test.geojson'
    output = args.output or ROOT / 'data/raw' / default_name
    write_json(output, result)
    print(f'Retrieved {len(features)} features. Saved {output}')
    print(json.dumps(features[0].get('properties', {}), indent=2))


if __name__ == '__main__':
    run_cli(main, error_hint='Check network access to geospatial.alberta.ca and the selected layer.')
