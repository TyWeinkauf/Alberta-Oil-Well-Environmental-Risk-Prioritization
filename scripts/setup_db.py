"""Apply missing migrations; running this again is safe and does not reset data."""
from _bootstrap import run_cli
from sqlalchemy import create_engine, text

from src.config import database_url
from src.db.migrations import migrate


def main():
    engine = create_engine(database_url(), pool_pre_ping=True)
    try:
        applied = migrate(engine)
        with engine.connect() as conn:
            version = conn.execute(text('SELECT postgis_version()')).scalar_one()
        print(f'Migrations applied: {applied or "none (already current)"}; PostGIS {version}')
    finally:
        engine.dispose()


if __name__ == '__main__':
    run_cli(main)
