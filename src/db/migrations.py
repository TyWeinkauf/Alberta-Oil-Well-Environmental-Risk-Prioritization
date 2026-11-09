"""Transactional SQL migrations with a lock and immutable applied-file checksums."""
import hashlib
from pathlib import Path

from sqlalchemy import Engine, text

from src.db.workflow import serialized_workflow

from src.config import ROOT


@serialized_workflow
def migrate(engine: Engine, directory: Path | None = None) -> list[str]:
    files = sorted((directory or ROOT / 'sql/migrations').glob('*.sql'))
    if not files:
        raise ValueError('No SQL migrations found')
    applied = []
    # No destructive reset: migration records and schema updates commit together.
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('alberta-screening-migrations'))"))
        version = int(conn.execute(text('SHOW server_version_num')).scalar_one())
        if not 170000 <= version < 180000:
            raise ValueError('This development workflow requires PostgreSQL 17')
        conn.execute(text('CREATE SCHEMA IF NOT EXISTS screening'))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS screening.schema_migrations (
            filename text PRIMARY KEY, checksum text NOT NULL,
            applied_at timestamptz NOT NULL DEFAULT now())'''))
        for path in files:
            payload = path.read_bytes()
            checksum = hashlib.sha256(payload).hexdigest()
            previous = conn.execute(text(
                'SELECT checksum FROM screening.schema_migrations WHERE filename=:name'
            ), {'name': path.name}).scalar_one_or_none()
            if previous is not None:
                if previous != checksum:
                    raise ValueError(f'Applied migration changed: {path.name}; add a new migration instead')
                continue
            conn.exec_driver_sql(payload.decode('utf-8'))
            conn.execute(text('INSERT INTO screening.schema_migrations VALUES (:name, :sha, now())'),
                         {'name': path.name, 'sha': checksum})
            applied.append(path.name)
        conn.execute(text('SELECT postgis_version()')).scalar_one()
    return applied
