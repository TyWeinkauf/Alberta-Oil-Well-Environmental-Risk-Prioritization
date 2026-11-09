"""Run bounded verified-source acquisition; disabled catalogue placeholders fail preflight."""
import argparse
import json
from pathlib import Path

from _bootstrap import run_cli
from sqlalchemy import create_engine

from src.config import ROOT, database_url, load_source_catalog, load_study_area
from src.sources.http import HttpCache
from src.sources.pipeline import run_live


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study-area',type=Path,default=ROOT/'config/study_area.live.yml')
    parser.add_argument('--catalog',type=Path,help='Source catalogue; local paths resolve relative to this YAML file')
    parser.add_argument('--refresh',action='store_true',help='Check remote sources again with cache validators')
    parser.add_argument('--max-records',type=int,default=10000)
    parser.add_argument('--max-download-mib',type=int,default=512)
    args=parser.parse_args()
    if not 1<=args.max_download_mib<=4096:
        raise ValueError('Download cap must be between 1 and 4096 MiB per response')
    engine=create_engine(database_url(),pool_pre_ping=True)
    try:
        report=run_live(engine,catalog=load_source_catalog(args.catalog),area=load_study_area(args.study_area),refresh=args.refresh,max_records=args.max_records,
                        cache=HttpCache(max_bytes=args.max_download_mib*1024**2),progress=lambda stage:print(stage,flush=True))
        print(json.dumps({'run_id':report['run_id'],'counts':report['counts']},indent=2))
    finally:
        engine.dispose()


if __name__=='__main__':
    run_cli(main,error_hint='Check verified source metadata/licences, network allowlist and PostgreSQL/PostGIS; see docs/source_verification.md.')
