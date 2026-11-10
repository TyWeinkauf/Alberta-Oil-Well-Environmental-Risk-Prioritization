"""Import the configured study-area waterways with a 500 m analysis margin."""
import argparse
import json
from pathlib import Path

from _bootstrap import run_cli
from sqlalchemy import create_engine
from src.config import ROOT, database_url, load_source_catalog, load_study_area
from src.sources.hydrography import import_waterways


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path)
    parser.add_argument('--study-area', type=Path, default=ROOT / 'config/study_area.live.yml')
    parser.add_argument('--include-seasonal', action='store_true', help='Include verified optional water sources')
    parser.add_argument('--refresh', action='store_true', help='Recheck source bytes; previous inventories remain readable')
    parser.add_argument('--max-records', type=int, default=10000)
    args = parser.parse_args()
    engine = create_engine(database_url(), pool_pre_ping=True, connect_args={'connect_timeout': 5})
    try:
        report = import_waterways(engine, catalog=load_source_catalog(args.catalog),
            area=load_study_area(args.study_area), include_optional=args.include_seasonal,
            refresh=args.refresh, max_records=args.max_records, progress=lambda stage: print(stage, flush=True))
        print(json.dumps({key: report[key] for key in ('import_id','feature_count','quarantined_count','coverage_status','reused')}, indent=2))
    finally:
        engine.dispose()


if __name__ == '__main__':
    run_cli(main, error_hint='Check DATABASE_URL, water catalogue metadata and network access; previous data is preserved.')
