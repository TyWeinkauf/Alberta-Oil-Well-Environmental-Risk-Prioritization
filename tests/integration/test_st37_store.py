"""Database verification for the unpublished ST37 source inventory."""
from pathlib import Path

import pytest
from sqlalchemy import text

from src.config import ROOT, load_study_area
from src.db.st37 import import_st37
from src.sources.st37 import prepare_st37
from tests.st37_helpers import synthetic_row, write_workbook

pytestmark = pytest.mark.integration


def test_st37_inventory_keeps_rejects_preserves_ids_and_reuses_import_without_publishing(test_engine, tmp_path):
    path = write_workbook(tmp_path / 'source.xlsx', [synthetic_row('0000001'),
        synthetic_row('0000002', SH_Actual_Longitude='invalid')])
    report = prepare_st37(path, load_study_area(ROOT / 'config/study_area.live.yml'), tmp_path / 'output')
    report_path = Path(report['artifacts']['inventory']['path']).with_name('report.json')
    args = {'license_note': 'Synthetic fixture only', 'coordinate_crs': 'EPSG:4269',
            'crs_evidence': 'Synthetic fixture coordinates declared NAD83'}
    first = import_st37(test_engine, report_path, **args)
    assert (first['records'], first['accepted'], first['quarantined'], first['geometries']) == (2, 1, 1, 1)
    second = import_st37(test_engine, report_path, **args)
    assert second['reused'] and first['import_id'] == second['import_id']
    assert not second['screening_run_published']
    with test_engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM screening.pipeline_runs')).scalar_one() == 0
        row = conn.execute(text('''SELECT well_licence_number,ST_SRID(geom),ST_X(ST_Transform(geom,4269))
            FROM screening.st37_surface_holes WHERE geom IS NOT NULL''')).one()
        assert row[0] == '0000001' and row[1] == 3400 and row[2] == pytest.approx(-115.0)
        assert conn.execute(text('SELECT raw_payload->>\'SH_Actual_Longitude\' FROM screening.st37_surface_holes WHERE geom IS NULL')).scalar_one() == 'invalid'
    raw_only = import_st37(test_engine, report_path, license_note='Synthetic fixture only')
    assert raw_only['geometries'] == 0 and raw_only['records'] == 2


def test_st37_failed_insert_rolls_back_without_removing_previous_inventory(test_engine, tmp_path):
    path = write_workbook(tmp_path / 'source.xlsx', [synthetic_row()])
    report = prepare_st37(path, load_study_area(ROOT / 'config/study_area.live.yml'), tmp_path / 'output')
    report_path = Path(report['artifacts']['inventory']['path']).with_name('report.json')
    first = import_st37(test_engine, report_path, license_note='Synthetic fixture only')
    with test_engine.begin() as conn:
        conn.execute(text("ALTER TABLE screening.st37_surface_holes ADD CONSTRAINT forced_failure CHECK (licensee_name <> 'Synthetic Licensee') NOT VALID"))
    with pytest.raises(Exception):
        import_st37(test_engine, report_path, license_note='Changed declaration forces a new snapshot')
    with test_engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM screening.st37_imports')).scalar_one() == 1
        assert conn.execute(text('SELECT count(*) FROM screening.st37_surface_holes')).scalar_one() == 1
    assert import_st37(test_engine, report_path, license_note='Synthetic fixture only')['import_id'] == first['import_id']
