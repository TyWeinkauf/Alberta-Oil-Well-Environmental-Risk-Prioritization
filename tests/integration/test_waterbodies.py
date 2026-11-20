"""Province inventory, transactional rejection handling and ST37/PostGIS comparison."""
import json
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import text
from streamlit.testing.v1 import AppTest

from src.config import ROOT, load_study_area
from src.db.st37 import import_st37
from src.db.waterbodies import (
    compare_st37_waterbodies, latest_province_waterbodies, waterbody_comparison_summary, waterbody_result,
)
from src.sources.http import HttpCache
from src.sources.hydrography import latest_water_import
from src.sources.st37 import prepare_st37
from src.sources.waterbodies import PROVINCE_STREAM_SCOPE, import_province_streams, import_province_waterbodies
from src.ui import waterbody_workflow
from tests.hydro_helpers import hydro_service
from tests.st37_helpers import synthetic_row, write_workbook

pytestmark = pytest.mark.integration


def test_province_pages_preserve_every_id_then_compare_verified_wells(test_engine, tmp_path, monkeypatch):
    with hydro_service() as (catalog, simulator):
        source = catalog.sources[0].model_copy(update={'layer_id': 72, 'arcgis_where': '1=1', 'arcgis_batch_size': 2})
        cache = HttpCache(tmp_path / 'cache')
        first = import_province_waterbodies(test_engine, source=source, cache=cache)
        assert (first['feature_count'], first['quarantined_count'], first['coverage_status']) == (2, 1, 'incomplete')
        assert {'7,10', '12'} <= {query['objectIds'][0] for query in simulator['queries'] if 'objectIds' in query}
        assert all(query.get('where') == ['1=1'] and 'geometry' not in query for query in simulator['queries'])
        assert latest_water_import(test_engine) is None
        repeated = import_province_waterbodies(test_engine, source=source, cache=cache)
        assert repeated['reused'] and repeated['import_id'] == first['import_id']
        simulator['missing_page'] = True
        with pytest.raises(ValueError, match='missing, duplicate or unexpected'):
            import_province_waterbodies(test_engine, source=source, cache=cache)
        with test_engine.connect() as conn:
            assert conn.execute(text('SELECT count(*) FROM screening.water_imports')).scalar_one() == 1
            reject = conn.execute(text('SELECT source_feature_id,payload FROM screening.water_feature_rejects')).one()
            assert reject.source_feature_id == '12' and reject.payload['_source_properties']['FEATURE_TYPE'] == 'RESERVOIR'
    workbook = write_workbook(tmp_path / 'st37.xlsx', [
        synthetic_row('0000012'), synthetic_row('0000013', SH_Actual_Latitude=53.29),
    ])
    preparation = prepare_st37(workbook, load_study_area(), tmp_path / 'st37')
    report = Path(preparation['artifacts']['inventory']['path']).with_name('report.json')
    raw = import_st37(test_engine, report, license_note='Synthetic test workbook')
    water_id = UUID(first['import_id'])
    with pytest.raises(ValueError, match='verified coordinate evidence'):
        compare_st37_waterbodies(test_engine, UUID(raw['import_id']), water_id)
    verified = import_st37(test_engine, report, license_note='Synthetic test workbook', coordinate_crs='EPSG:4326',
                           crs_evidence='Synthetic test coordinates explicitly declared WGS84')
    well_id = UUID(verified['import_id'])
    comparison = compare_st37_waterbodies(test_engine, well_id, water_id)
    assert compare_st37_waterbodies(test_engine, well_id, water_id) == comparison
    assert latest_province_waterbodies(test_engine)['comparison_id'] == comparison
    summary = waterbody_comparison_summary(test_engine, comparison)
    assert summary['well_count'] == 2 and summary['within_50'] == 1 and summary['unknown_within_500'] == 1
    match = waterbody_result(test_engine, comparison, '0000012')
    assert match['observed_distance_m'] == 0 and match['nearest_source_feature_id'] == '10'
    unmatched = waterbody_result(test_engine, comparison, '0000013')
    assert unmatched['result_state'] == 'unknown_incomplete_coverage'
    with test_engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM screening.pipeline_runs')).scalar_one() == 0
    monkeypatch.setenv('DATABASE_URL', test_engine.url.render_as_string(hide_password=False))
    app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=20)
    app.query_params['dataset_mode'] = 'PostGIS workflows'
    app.run()
    app.checkbox(key='province_water_comparison').check().run()
    assert not app.exception and any('2 ST37 wells' in element.value for element in app.caption)
    app.text_input(key='province_water_licence').input('0000012').run()
    assert not app.exception
    assert any('well_licence_number' in frame.value and frame.value['well_licence_number'].tolist() == ['0000012']
               for frame in app.dataframe)


def test_app_buttons_load_inputs_and_compare_with_read_only_reruns(test_engine, tmp_path, monkeypatch):
    workbook = write_workbook(tmp_path / 'ST37_SH.xlsx', [synthetic_row('0000012')])
    monkeypatch.setattr(waterbody_workflow, 'ST37_WORKBOOK', workbook)
    monkeypatch.setattr(waterbody_workflow, 'ST37_RAW_ROOT', tmp_path / 'raw')
    monkeypatch.setenv('DATABASE_URL', test_engine.url.render_as_string(hide_password=False))
    with hydro_service() as (catalog, simulator):
        source = catalog.sources[0].model_copy(update={'layer_id': 72, 'arcgis_where': '1=1', 'arcgis_batch_size': 2})
        cache = HttpCache(tmp_path / 'http')

        def load_water(engine, *, progress):
            return import_province_waterbodies(engine, source=source, cache=cache, progress=progress)

        monkeypatch.setattr(waterbody_workflow, 'import_province_waterbodies', load_water)
        app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=20)
        app.query_params['dataset_mode'] = 'PostGIS workflows'
        app.run()
        app.checkbox(key='province_water_comparison').check().run()
        assert not app.exception and not app.session_state.actions and simulator['requests'] == 0
        assert app.button(key='compare_waterbodies').disabled
        with test_engine.connect() as conn:
            assert conn.execute(text("SELECT to_regnamespace('screening')")).scalar_one() is None

        app.button(key='import_province_waterbodies').click().run()
        assert not app.exception and not app.error
        water_id = app.selectbox(key='province_water_snapshot').value
        assert water_id is not None and app.button(key='compare_waterbodies').disabled
        app.button(key='import_st37_workbook').click().run()
        raw_id = app.selectbox(key='province_well_snapshot').value
        assert raw_id is not None and app.button(key='compare_waterbodies').disabled
        report_path = next((tmp_path / 'raw').glob('*/report.json'))
        relocated = json.loads(report_path.read_text(encoding='utf-8'))
        for entry in relocated['artifacts'].values():
            entry['path'] = str(tmp_path / 'old-workspace' / Path(entry['path']).name)
        report_path.write_text(json.dumps(relocated), encoding='utf-8')
        app.text_input(key='st37_coordinate_crs').input('EPSG:4326').run()
        assert app.button(key='import_st37_workbook').disabled
        app.text_area(key='st37_crs_evidence').input('Declared WGS84 for the test workbook').run()
        assert app.button(key='compare_waterbodies').disabled
        assert len(app.session_state.actions) == 2
        app.button(key='import_st37_workbook').click().run()
        well_id = app.selectbox(key='province_well_snapshot').value
        assert not app.exception and not app.error and well_id != raw_id
        assert any('Reusing a verified ST37 preparation' in item.value for item in app.text)
        assert not app.button(key='compare_waterbodies').disabled
        app.button(key='compare_waterbodies').click().run()
        assert not app.exception and not app.error
        app.text_input(key='province_water_licence').input('0000012').run()
        assert any('well_licence_number' in frame.value and frame.value['well_licence_number'].tolist() == ['0000012']
                   for frame in app.dataframe)
        requests = simulator['requests']
        app.run()
        assert not app.exception and len(app.session_state.actions) == 4 and simulator['requests'] == requests
        app.selectbox(key='province_well_snapshot').select(raw_id).run()
        assert not app.exception and app.button(key='compare_waterbodies').disabled
        app.selectbox(key='province_well_snapshot').select(well_id).run()
        simulator['missing_page'] = True
        app.button(key='import_province_waterbodies').click().run()
        assert not app.exception and app.error
        assert app.selectbox(key='province_water_snapshot').value == water_id
        assert any('1 ST37 wells' in element.value for element in app.caption)
        with test_engine.connect() as conn:
            assert conn.execute(text('SELECT count(*) FROM screening.st37_imports')).scalar_one() == 2
            assert conn.execute(text('SELECT count(*) FROM screening.water_imports')).scalar_one() == 1
            assert conn.execute(text('SELECT count(*) FROM screening.waterbody_comparisons')).scalar_one() == 1


def test_app_can_import_and_compare_province_streams(test_engine, tmp_path, monkeypatch):
    workbook = write_workbook(tmp_path / 'fixture.xlsx', [synthetic_row('0000012')])
    preparation = prepare_st37(workbook, load_study_area(), tmp_path / 'inventory')
    report = Path(preparation['artifacts']['inventory']['path']).with_name('report.json')
    wells = import_st37(test_engine, report, license_note='Synthetic test workbook', coordinate_crs='EPSG:4326',
                        crs_evidence='Declared WGS84 for test workbook')
    monkeypatch.setenv('DATABASE_URL', test_engine.url.render_as_string(hide_password=False))
    with hydro_service() as (catalog, simulator):
        polygons = catalog.sources[0].model_copy(update={'layer_id': 72, 'arcgis_where': '1=1'})
        water = import_province_waterbodies(test_engine, source=polygons, cache=HttpCache(tmp_path / 'water-cache'))
        source = catalog.sources[1].model_copy(update={'layer_id': 107, 'arcgis_where': '1=1', 'arcgis_batch_size': 2})
        cache = HttpCache(tmp_path / 'stream-cache')

        def load_streams(engine, *, progress):
            return import_province_streams(engine, source=source, cache=cache, progress=progress)

        monkeypatch.setattr(waterbody_workflow, 'import_province_streams', load_streams)
        app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=20)
        app.query_params['dataset_mode'] = 'PostGIS workflows'
        app.run()
        requests = simulator['requests']
        app.checkbox(key='province_water_comparison').check().run()
        assert not app.exception and simulator['requests'] == requests
        app.button(key='import_province_streams').click().run()
        assert not app.exception and not app.error
        streams_id = app.selectbox(key='province_water_snapshot').value
        assert streams_id != UUID(water['import_id'])
        assert latest_water_import(test_engine) is None
        with test_engine.connect() as conn:
            stage = conn.execute(text('''SELECT feature_count,quarantined_count,manifest->>'scope' AS scope
                FROM screening.water_imports WHERE import_id=:id'''), {'id': streams_id}).one()
            assert tuple(stage) == (2, 1, PROVINCE_STREAM_SCOPE)
            stored = conn.execute(text('''SELECT source_feature_id, GeometryType(geom)
                FROM screening.water_features WHERE import_id=:id ORDER BY source_feature_id'''),
                {'id': streams_id}).all()
            assert stored == [('10', 'LINESTRING'), ('7', 'LINESTRING')]
        assert app.button(key='compare_waterbodies').label == 'Run stream comparison'
        app.button(key='compare_waterbodies').click().run()
        assert not app.exception and not app.error
        comparison_id = compare_st37_waterbodies(test_engine, UUID(wells['import_id']), streams_id)
        row = waterbody_result(test_engine, comparison_id, '0000012')
        assert row['nearest_source_feature_id'] == '10'
        assert 0 < row['observed_distance_m'] < 50
        requests = simulator['requests']
        app.run()
        assert simulator['requests'] == requests
        app.selectbox(key='province_water_snapshot').select(UUID(water['import_id'])).run()
        assert not app.exception and app.button(key='compare_waterbodies').label == 'Run waterbody comparison'
