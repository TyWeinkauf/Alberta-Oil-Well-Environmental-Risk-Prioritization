"""Serialize application mutations across processes; PostgreSQL releases dead-session locks."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

from sqlalchemy import text

LOCK_NAME = 'alberta-screening-workflow'
_held_engines = ContextVar('alberta_workflow_engines', default=frozenset())


class WorkflowBusy(ValueError):
    """Another process owns the mutation workflow for this database."""


@contextmanager
def workflow_lock(engine):
    # Public workflows compose seed/migration/analysis/import functions on one engine.
    held = _held_engines.get()
    if engine in held:
        yield
        return
    with engine.connect() as conn:
        acquired = conn.execute(text('SELECT pg_try_advisory_lock(hashtext(:name))'),
                                {'name': LOCK_NAME}).scalar_one()
        if not acquired:
            raise WorkflowBusy('Another import, migration or analysis is running. Wait for it to finish, then retry.')
        token = _held_engines.set(held | {engine})
        try:
            conn.commit()
            # Only the exclusive owner can classify attempts left by a stopped process.
            if conn.execute(text("SELECT to_regclass('screening.pipeline_attempts')")).scalar_one():
                conn.execute(text('''UPDATE screening.pipeline_attempts SET status='failed',finished_at=now(),
                    error_code='InterruptedWorkflow',
                    error_summary='Previous workflow stopped before recording completion. Inspect committed results and rerun to verify or repair reports.'
                    WHERE status='running' '''))
            conn.commit()
            yield
        finally:
            _held_engines.reset(token)
            try:
                conn.rollback()
                conn.execute(text('SELECT pg_advisory_unlock(hashtext(:name))'), {'name': LOCK_NAME})
                conn.commit()
            except Exception:
                # Never return a potentially locked session to the pool.
                conn.invalidate()
                raise


def serialized_workflow(action):
    @wraps(action)
    def guarded(engine, *args, **kwargs):
        with workflow_lock(engine):
            return action(engine, *args, **kwargs)
    return guarded
