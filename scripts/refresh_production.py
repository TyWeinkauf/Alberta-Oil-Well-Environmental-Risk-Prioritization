"""Refresh verified production for an explicit analysis run and month window."""
import argparse
import json
from _bootstrap import run_cli
from sqlalchemy import create_engine

from src.config import database_url
from src.production.store import refresh_production


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--start',required=True,help='First month, YYYY-MM')
    parser.add_argument('--end',required=True,help='Last month, YYYY-MM')
    args=parser.parse_args()
    engine=create_engine(database_url(),pool_pre_ping=True)
    try:
        report=refresh_production(engine,args.run_id,start=args.start,end=args.end)
        print(json.dumps({'batch_id':report['batch_id'],'validation':report['validation']},indent=2))
    finally:engine.dispose()


if __name__=='__main__':
    run_cli(main,error_hint='Check verified production metadata, network permissions and docs/production.md.')
