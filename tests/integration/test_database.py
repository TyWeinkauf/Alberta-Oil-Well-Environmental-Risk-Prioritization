import json
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from src.config import ROOT
from src.db.demo import seed_demo
from src.db.migrations import migrate

pytestmark = pytest.mark.integration


def seed(engine, tmp_path, fixture_path=None):
    kwargs = {'raw_root':tmp_path/'raw', 'output_root':tmp_path/'runs'}
    if fixture_path is not None:
        kwargs['fixture_path'] = fixture_path
    return seed_demo(engine, **kwargs)


def test_migrations_are_repeatable_and_detect_edited_history(test_engine, tmp_path):
    assert migrate(test_engine) == ['001_initial.sql','002_spatial_coverage.sql','003_live_attempts.sql']
    assert migrate(test_engine) == []
    with test_engine.connect() as conn:
        tables = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='screening'")).scalars().all()
        assert {'wells','environmental_features','source_snapshots','pipeline_runs','quarantine_records',
                'production_monthly','production_well_links','well_proximity'} <= set(tables)
    migration = ROOT / 'sql/migrations/001_initial.sql'
    (tmp_path/migration.name).write_text(migration.read_text()+'\n-- unexpected edit\n')
    with pytest.raises(ValueError, match='Applied migration changed'):
        migrate(test_engine, tmp_path)
    assert migrate(test_engine) == []


def test_seed_audit_and_idempotent_rerun(test_engine, tmp_path):
    migrate(test_engine)
    first = seed(test_engine, tmp_path)
    second = seed(test_engine, tmp_path)
    assert first == second
    assert first['status'] == 'seeded'
    assert first['counts'] == {'wells':2,'environmental_features':2,'quarantine_records':6,
                               'production_monthly':0,'well_proximity':0}
    assert first['validation']['input_records'] == 10
    assert first['validation']['accepted_records'] == 4
    report = tmp_path/'runs'/first['run_id']/'manifest.json'
    assert json.loads(report.read_text()) == first
    with test_engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM screening.pipeline_runs')).scalar_one() == 1
        assert conn.execute(text('SELECT count(*) FROM screening.source_snapshots')).scalar_one() == 1
        assert conn.execute(text('SELECT DISTINCT ST_SRID(geom) FROM screening.wells')).scalar_one() == 3400
        assert conn.execute(text('SELECT count(*) FROM screening.wells WHERE operator_name_if_verified IS NOT NULL')).scalar_one() == 0
        references = conn.execute(text('SELECT raw_payload_reference FROM screening.quarantine_records')).scalars()
        for reference in references:
            path, row = reference.split('#')
            raw = json.loads(Path(path).read_text())
            entity, index = row.split('/')
            assert raw[entity][int(index)] is not None


def test_database_constraints_reject_duplicate_ids_and_wrong_geometry(test_engine, tmp_path):
    migrate(test_engine)
    seed(test_engine, tmp_path)
    with pytest.raises(IntegrityError):
        with test_engine.begin() as conn:
            conn.execute(text('''INSERT INTO screening.wells (source_well_id,snapshot_id,geom)
                SELECT source_well_id,snapshot_id,geom FROM screening.wells LIMIT 1'''))
    with pytest.raises(DBAPIError, match='Geometry type'):
        with test_engine.begin() as conn:
            conn.execute(text('''INSERT INTO screening.wells (source_well_id,snapshot_id,geom)
                SELECT 'WRONG-GEOMETRY',snapshot_id,ST_GeomFromText('LINESTRING(0 0,1 1)',3400)
                FROM screening.wells LIMIT 1'''))


def test_unknown_crs_does_not_damage_previous_seed(test_engine, tmp_path):
    migrate(test_engine)
    first = seed(test_engine, tmp_path)
    fixture = json.loads((ROOT/'tests/fixtures/demo.json').read_text())
    fixture['crs'] = None
    broken = tmp_path/'unknown-crs.json'
    broken.write_text(json.dumps(fixture))
    with pytest.raises(ValueError, match='CRS is required'):
        seed(test_engine, tmp_path, broken)
    assert seed(test_engine, tmp_path) == first


def test_insert_failure_rolls_back_entire_new_run(test_engine, tmp_path):
    migrate(test_engine)
    with test_engine.begin() as conn:
        conn.exec_driver_sql('''CREATE FUNCTION screening.reject_fixture() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic load failure'; END; $$;
            CREATE TRIGGER reject_fixture BEFORE INSERT ON screening.environmental_features
            FOR EACH ROW EXECUTE FUNCTION screening.reject_fixture();''')
    with pytest.raises(DBAPIError, match='synthetic load failure'):
        seed(test_engine, tmp_path)
    with test_engine.connect() as conn:
        for table in ['pipeline_runs','source_snapshots','wells','environmental_features','quarantine_records']:
            assert conn.execute(text(f'SELECT count(*) FROM screening.{table}')).scalar_one() == 0
    with test_engine.begin() as conn:
        conn.exec_driver_sql('DROP TRIGGER reject_fixture ON screening.environmental_features')
    assert seed(test_engine, tmp_path)['counts']['wells'] == 2


def test_corrupt_cache_is_not_overwritten(test_engine, tmp_path):
    migrate(test_engine)
    first = seed(test_engine, tmp_path)
    path = Path(first['source']['raw_payload_reference'])
    path.write_text('corrupt local cache')
    with pytest.raises(ValueError, match='checksum mismatch'):
        seed(test_engine, tmp_path)
    assert path.read_text() == 'corrupt local cache'


def test_failed_migration_rolls_back_schema_and_ledger(test_engine, tmp_path):
    (tmp_path/'001_broken.sql').write_text(
        'CREATE TABLE screening.partial (id int); SELECT * FROM screening.missing_table;')
    with pytest.raises(DBAPIError):
        migrate(test_engine, tmp_path)
    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT to_regnamespace('screening')")).scalar_one() is None
