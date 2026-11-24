"""Create a small, reproducible classroom package from a retained ST37 report and inventory."""
import argparse
import json
from datetime import date
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine

from _bootstrap import run_cli
from src.config import ROOT, database_url
from src.demo.data import DEFAULT_PACKAGE, SYNTHETIC_PACKAGE, prepare_package
from src.demo.hydrography import extract_imported_water
from src.demo.regions import load_regions
from src.demo.spatial import WATER_PROVENANCE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True,
                        help='ST37 preparation report beside its retained inventory.csv')
    parser.add_argument('--regions', type=Path, default=ROOT / 'config/demo_regions.yml')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--waterbodies-import-id', type=UUID, help='Use this existing layer-72 waterbody snapshot')
    parser.add_argument('--streams-import-id', type=UUID, help='Use this existing layer-107 stream snapshot')
    parser.add_argument('--coordinate-crs', help='Verified geographic EPSG CRS of the workbook columns')
    parser.add_argument('--crs-evidence', help='Publisher metadata or written confirmation for the workbook datum')
    parser.add_argument('--release-date', type=date.fromisoformat,
                        help='Verified publisher release date (YYYY-MM-DD)')
    args = parser.parse_args()
    if bool(args.waterbodies_import_id) != bool(args.streams_import_id):
        parser.error('Provide both water import IDs to build a real-water package')
    regions = load_regions(args.regions)
    hydrography = None
    if args.waterbodies_import_id:
        engine = create_engine(database_url(), connect_args={'connect_timeout': 5})
        try:
            hydrography = extract_imported_water(engine, regions, args.waterbodies_import_id, args.streams_import_id)
        finally:
            engine.dispose()
    output = args.output or (DEFAULT_PACKAGE if hydrography else SYNTHETIC_PACKAGE)
    if not hydrography and output.resolve() == DEFAULT_PACKAGE:
        parser.error('The default classroom package requires both water import IDs')
    package = prepare_package(args.report, regions, output,
                              coordinate_crs=args.coordinate_crs, crs_evidence=args.crs_evidence,
                              release_date=args.release_date, hydrography=hydrography)
    print(json.dumps({
        'path': str(output.resolve()), 'bytes': output.stat().st_size,
        'package_id': package['package_id'], 'readiness': package['manifest']['readiness'],
        'regions': {key: {'candidates': group['candidate_count'], 'selected': len(group['wells']),
                          'imported_water_features': sum(f['provenance'] == WATER_PROVENANCE for f in group['features']),
                          'synthetic_features': sum(f['provenance'] != WATER_PROVENANCE for f in group['features'])}
                    for key, group in package['regions'].items()},
    }, indent=2))


if __name__ == '__main__':
    run_cli(main, error_hint='Check the retained report, inventory and classroom coordinate evidence.')
