"""Store or query a water-only ST37 proximity comparison in PostGIS."""
import argparse
import json
from uuid import UUID

from _bootstrap import run_cli
from sqlalchemy import create_engine
from src.config import database_url
from src.db.waterbodies import compare_st37_waterbodies, waterbody_comparison_summary, waterbody_result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--st37-import-id', type=UUID)
    parser.add_argument('--water-import-id', type=UUID)
    parser.add_argument('--comparison-id', type=UUID, help='Read an existing comparison without writing')
    parser.add_argument('--licence', help='Return a specific textual licence number, including leading zeros')
    args = parser.parse_args()
    comparison_id = args.comparison_id
    if (comparison_id and (args.st37_import_id or args.water_import_id)) or (
        not comparison_id and not (args.st37_import_id and args.water_import_id)
    ):
        parser.error('Provide --comparison-id or both --st37-import-id and --water-import-id')
    engine = create_engine(database_url(), pool_pre_ping=True, connect_args={'connect_timeout': 5})
    try:
        if comparison_id is None:
            comparison_id = compare_st37_waterbodies(engine, args.st37_import_id, args.water_import_id)
        result = (waterbody_result(engine, comparison_id, args.licence) if args.licence
                  else waterbody_comparison_summary(engine, comparison_id))
        if result is None:
            raise ValueError('Licence was not found in the selected ST37 comparison')
        print(json.dumps(result, indent=2, default=str))
    finally:
        engine.dispose()


if __name__ == '__main__':
    run_cli(main, error_hint='Check DATABASE_URL and the selected PostGIS imports.')
