"""Explicit user actions; filtering and Streamlit reruns never invoke this workflow."""
from collections.abc import Callable

from sqlalchemy import Engine, text

from src.db.workflow import serialized_workflow

from src.db.demo import seed_demo
from src.db.migrations import migrate
from src.spatial.engine import analyze_run


@serialized_workflow
def run_demo(engine: Engine, progress: Callable[[str],None] = lambda _: None) -> str:
    progress('Preflight: checking PostgreSQL/PostGIS and schema')
    with engine.connect() as conn:
        conn.execute(text('SELECT 1')).scalar_one()
    migrate(engine)
    progress('Loading and validating synthetic inputs')
    report = seed_demo(engine)
    progress('Calculating proximity and coverage results')
    analyze_run(engine,report['run_id'])
    progress('Ready: demo results can be inspected and exported')
    return report['run_id']
