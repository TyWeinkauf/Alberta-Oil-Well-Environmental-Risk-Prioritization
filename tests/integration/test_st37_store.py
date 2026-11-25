"""Database verification for the unpublished ST37 source inventory."""
from pathlib import Path

import pytest
from sqlalchemy import text
from streamlit.testing.v1 import AppTest

from src.config import ROOT, load_study_area
from src.db.st37 import import_st37, st37_inventory_filter_options
from src.sources.st37 import prepare_st37
from src.ui import waterbody_workflow
from tests.st37_helpers import synthetic_row, write_workbook

pytestmark = pytest.mark.integration


def test_app_imports_and_browses_st37_without_a_water_snapshot(test_engine, tmp_path, monkeypatch):
    wells = [synthetic_row(f'{number:07}') for number in range(1, 101)]
    wells[0] = synthetic_row('0000001', Licensee='Another Licensee', Licence_Status='Suspended')
    wells.append(synthetic_row('0000101', SH_Actual_Longitude='invalid', Licensee='Another Licensee',
                               Energy_Devlpmt_Category_Type='Alternate category'))
    workbook = write_workbook(tmp_path / 'ST37_SH.xlsx', wells)
    monkeypatch.setattr(waterbody_workflow, 'ST37_WORKBOOK', workbook)
    monkeypatch.setattr(waterbody_workflow, 'ST37_RAW_ROOT', tmp_path / 'raw')
    monkeypatch.setenv('DATABASE_URL', test_engine.url.render_as_string(hide_password=False))
    app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=30)
    app.query_params['dataset_mode'] = 'ST37 well inventory'
    app.run()
    assert not app.exception and not app.error and not app.dataframe
    assert not app.sidebar.expander and not app.sidebar.text_input
    assert not app.sidebar.text_area and not app.sidebar.date_input
    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT to_regnamespace('screening')")).scalar_one() is None

    app.button(key='import_st37_workbook').click().run()
    assert not app.exception and not app.error
    table = app.dataframe[0].value
    assert len(table) == 100 and table['Well_Licence_Number'].iloc[0] == '0000001'
    assert table['Water proximity band'].eq('Unavailable').all()
    assert table['Observed water distance (m)'].isna().all()
    assert any('101 workbook rows · 100 accepted · 1 quarantined' in caption.value for caption in app.caption)
    app.number_input[0].set_value(2).run()
    last = app.dataframe[0].value.iloc[0]
    assert last['Well_Licence_Number'] == '0000101' and last['SH_Actual_Longitude'] == 'invalid'
    assert last['Validation errors']

    snapshot_id = app.session_state.st37_inventory_snapshot
    assert st37_inventory_filter_options(test_engine, snapshot_id, 'licensee_name', 'aNoThEr') == ['Another Licensee']
    licensees, statuses, categories, bands = app.multiselect
    licensee_key, status_key, category_key, band_key = licensees.key, statuses.key, categories.key, bands.key
    assert licensee_key is not None and status_key is not None and category_key is not None and band_key is not None
    assert bands.options == ['Unavailable']
    bands.set_value(['unavailable']).run()
    assert len(app.dataframe[0].value) == 100
    app.multiselect(key=licensee_key).set_value(['Another Licensee']).run()
    assert app.number_input[0].value == 1
    assert app.dataframe[0].value['Well_Licence_Number'].tolist() == ['0000001', '0000101']
    assert any('2 matching workbook records' in caption.value for caption in app.caption)
    app.multiselect(key=status_key).set_value(['Issued']).run()
    app.multiselect(key=category_key).set_value(['Synthetic category']).run()
    assert not app.dataframe and any('No workbook records match the selected filters' in alert.value for alert in app.info)
    app.multiselect(key=category_key).set_value(['Alternate category']).run()
    assert app.dataframe[0].value['Well_Licence_Number'].tolist() == ['0000101']
    app.text_input(key='st37_inventory_licence').input('0000001').run()
    assert not app.dataframe and any('match the licence and selected filters' in alert.value for alert in app.info)
    app.text_input(key='st37_inventory_licence').input('0000101').run()
    assert app.dataframe[0].value['Well_Licence_Number'].tolist() == ['0000101']
    for key in (licensee_key, status_key, category_key, band_key):
        app.multiselect(key=key).set_value([]).run()

    app.text_input(key='st37_inventory_licence').input('0000007').run()
    assert app.dataframe[0].value['Well_Licence_Number'].tolist() == ['0000007']
    app.text_input(key='st37_inventory_licence').input('7').run()
    assert not app.exception and not app.dataframe and any('No rows match' in alert.value for alert in app.info)
    with test_engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM screening.st37_imports')).scalar_one() == 1
        assert conn.execute(text('SELECT count(*) FROM screening.water_imports')).scalar_one() == 0


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
