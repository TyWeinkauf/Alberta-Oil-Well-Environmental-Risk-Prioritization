"""Create a small, reproducible classroom package from a retained ST37 report and inventory."""
import argparse
import json
from pathlib import Path

from _bootstrap import run_cli
from src.config import ROOT
from src.demo.data import DEFAULT_PACKAGE, prepare_package
from src.demo.regions import load_regions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True,
                        help='ST37 preparation report beside its retained inventory.csv')
    parser.add_argument('--regions', type=Path, default=ROOT / 'config/demo_regions.yml')
    parser.add_argument('--output', type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument('--coordinate-crs', help='Verified geographic EPSG CRS of the workbook columns')
    parser.add_argument('--crs-evidence', help='Publisher metadata or written confirmation for the workbook datum')
    args = parser.parse_args()
    package = prepare_package(args.report, load_regions(args.regions), args.output,
                              coordinate_crs=args.coordinate_crs, crs_evidence=args.crs_evidence)
    print(json.dumps({
        'path': str(args.output.resolve()), 'bytes': args.output.stat().st_size,
        'package_id': package['package_id'], 'readiness': package['manifest']['readiness'],
        'regions': {key: {'candidates': group['candidate_count'], 'selected': len(group['wells']),
                          'synthetic_features': len(group['features'])}
                    for key, group in package['regions'].items()},
    }, indent=2))


if __name__ == '__main__':
    run_cli(main, error_hint='Check the retained report, inventory and classroom coordinate evidence.')
