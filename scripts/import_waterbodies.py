"""Import a provincial Alberta Base Water Feature inventory into PostGIS."""
import argparse
import json

from _bootstrap import run_cli
from sqlalchemy import create_engine
from src.config import database_url
from src.sources.waterbodies import MAX_RECORDS, import_province_streams, import_province_waterbodies


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    importers = {'waterbodies': import_province_waterbodies, 'streams': import_province_streams}
    parser.add_argument('--layer', choices=tuple(importers), default='waterbodies',
                        help='Choose layer 72 waterbody polygons or layer 107 stream lines')
    parser.add_argument('--max-records', type=int, default=MAX_RECORDS,
                        help='Abort before geometry transfer if the publisher count exceeds this guard')
    args = parser.parse_args()
    engine = create_engine(database_url(), pool_pre_ping=True, connect_args={'connect_timeout': 5})
    try:
        report = importers[args.layer](engine, max_records=args.max_records,
                                      progress=lambda message: print(message, flush=True))
        print(json.dumps({key: report[key] for key in ('import_id', 'feature_count', 'quarantined_count',
                                                       'coverage_status', 'reused')}, indent=2))
    finally:
        engine.dispose()


if __name__ == '__main__':
    run_cli(main, error_hint='Check DATABASE_URL, storage budget and access to Alberta ArcGIS.')
