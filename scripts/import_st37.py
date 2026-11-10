"""Load a prepared ST37 inventory into PostGIS without publishing proximity results."""
import argparse
import json
from pathlib import Path

from _bootstrap import run_cli
from sqlalchemy import create_engine
from src.artifacts import write_json
from src.config import ROOT, database_url
from src.db.st37 import import_st37


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--license-note', required=True)
    parser.add_argument('--coordinate-crs', help='Documented geographic CRS, e.g. EPSG:4269 for NAD83; never inferred from filename')
    parser.add_argument('--crs-evidence', help='Publisher metadata/reference supporting the coordinate datum')
    parser.add_argument('--downloaded-at', help='Actual download timestamp with timezone; omit if unknown')
    parser.add_argument('--release-date', help='Publisher release date YYYY-MM-DD; omit if unknown')
    args = parser.parse_args()
    engine = create_engine(database_url(), pool_pre_ping=True, connect_args={'connect_timeout': 5})
    try:
        result = import_st37(engine, args.report, license_note=args.license_note,
                             coordinate_crs=args.coordinate_crs, crs_evidence=args.crs_evidence,
                             downloaded_at=args.downloaded_at, release_date=args.release_date)
        write_json(ROOT / 'outputs/st37' / result['import_id'] / 'database_import.json', result)
        print(json.dumps(result, indent=2))
    finally:
        engine.dispose()


if __name__ == '__main__':
    run_cli(main, error_hint='Check the private DATABASE_URL, prepared report and docs/st37_excel.md. No credentials logged.')
