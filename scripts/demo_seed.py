"""Load the synthetic fixture into PostGIS and write its manifest/validation report."""
import json
from _bootstrap import run_cli
from sqlalchemy import create_engine

from src.config import database_url, load_source_catalog
from src.db.demo import seed_demo


def main():
    load_source_catalog()  # Catch malformed source configuration before touching data.
    engine = create_engine(database_url(), pool_pre_ping=True)
    try:
        report = seed_demo(engine)
        print(json.dumps({'run_id': report['run_id'], 'status': report['status'], 'counts': report['counts']}, indent=2))
        print(f'Reports: outputs/runs/{report["run_id"]}/manifest.json and validation.json')
    finally:
        engine.dispose()


if __name__ == '__main__':
    run_cli(main)
