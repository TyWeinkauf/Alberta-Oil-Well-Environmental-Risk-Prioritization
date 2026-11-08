"""Explicit synthetic production demo; never imports or claims real Petrinex records."""
import json
from _bootstrap import run_cli
from sqlalchemy import create_engine

from src.config import database_url
from src.orchestrator import run_demo
from src.production.store import load_demo_production


def main():
    engine=create_engine(database_url(),pool_pre_ping=True)
    try:
        run=run_demo(engine)
        report=load_demo_production(engine,run)
        print(json.dumps({'run_id':run,'batch_id':report['batch_id'],'source_mode':report['source_mode'],
                          'validation':report['validation']},indent=2))
    finally:engine.dispose()


if __name__=='__main__':run_cli(main)
