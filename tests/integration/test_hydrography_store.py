import pytest
from sqlalchemy import text
from streamlit.testing.v1 import AppTest

from src.config import ROOT, load_study_area
from src.sources.hydrography import import_waterways, latest_water_import, water_features
from src.sources.http import HttpCache
from tests.hydro_helpers import hydro_service

pytestmark = pytest.mark.integration


def run(engine, catalog, tmp_path, **kwargs):
    return import_waterways(engine, catalog=catalog, area=load_study_area(ROOT/'config/study_area.live.yml'),
        cache=HttpCache(tmp_path/'cache'), raw_root=tmp_path/'raw', output_root=tmp_path/'output', **kwargs)


def test_water_import_is_atomic_idempotent_keeps_raw_properties_and_separate_layer_ids(test_engine, tmp_path):
    with hydro_service() as (catalog, state):
        first = run(test_engine, catalog, tmp_path)
        requests = state['requests']
        assert first['feature_count'] == 2 and first['coverage_status'] == 'complete'
        repeat = run(test_engine, catalog, tmp_path)
        assert repeat['import_id'] == first['import_id'] and repeat['reused']
        assert state['requests'] == requests
        assert len(water_features(test_engine, first['import_id'])) == 2
        seasonal = run(test_engine, catalog, tmp_path, include_optional=True)
        assert seasonal['feature_count'] == 2 and len(seasonal['sources']) == 3
        assert seasonal['validation']['synthetic_water_2']['accepted'] == 0
        with test_engine.connect() as conn:
            assert conn.execute(text('SELECT count(*) FROM screening.pipeline_runs')).scalar_one() == 0
            assert conn.execute(text('SELECT count(*) FROM screening.environmental_features')).scalar_one() == 0
            rows = conn.execute(text('''SELECT ST_SRID(geom),ST_IsValid(geom),properties->>'SOURCE'
                FROM screening.water_features WHERE import_id=:id'''), {'id': first['import_id']}).all()
            assert len(rows) == 2 and all(row == (3400,True,'Synthetic raw attribute') for row in rows)
        state['missing_page'] = True
        with pytest.raises(ValueError, match='missing, duplicate or unexpected'):
            run(test_engine, catalog, tmp_path, refresh=True)
        assert latest_water_import(test_engine)['import_id'] == seasonal['import_id']


def test_water_invalid_geometry_reports_incomplete_coverage_and_failed_load_retains_prior(test_engine, tmp_path):
    with hydro_service() as (catalog, state):
        first = run(test_engine, catalog, tmp_path)
        state['invalid_geometry'] = True
        incomplete = run(test_engine, catalog, tmp_path, refresh=True)
        assert incomplete['coverage_status'] == 'incomplete' and incomplete['quarantined_count'] == 1
        assert incomplete['feature_count'] == 1 and incomplete['quarantines'][0]['raw_payload_reference']
        state['invalid_geometry'] = False
        state['revision'] = 'blocked'
        with test_engine.begin() as conn:
            conn.execute(text("ALTER TABLE screening.water_features ADD CONSTRAINT force_water_failure CHECK(name<>'blocked') NOT VALID"))
        with pytest.raises(Exception):
            run(test_engine, catalog, tmp_path, refresh=True)
        assert latest_water_import(test_engine)['import_id'] == incomplete['import_id']
        assert len(water_features(test_engine, first['import_id'])) == 2


def test_app_can_import_and_preview_water_before_wells_without_reimporting_on_rerun(test_engine, tmp_path, monkeypatch):
    import src.ui.water as water_ui
    monkeypatch.setenv('DATABASE_URL', test_engine.url.render_as_string(hide_password=False))
    with hydro_service() as (catalog, state):
        calls = []
        def importer(engine, **kwargs):
            calls.append(kwargs)
            return run(engine, catalog, tmp_path, include_optional=kwargs['include_optional'])
        monkeypatch.setattr(water_ui, 'import_waterways', importer)
        app = AppTest.from_file(str(ROOT/'app.py')).run(timeout=30)
        assert not app.exception
        app.button(key='import_waterways').click().run(timeout=30)
        assert not app.exception and len(calls) == 1
        assert any('Water inventory: 2 features' in item.value for item in app.caption)
        app.checkbox(key='water_preview').check().run(timeout=30)
        assert not app.exception and any(item.value == 'Imported waterways' for item in app.subheader)
        assert any(len(frame.value) == 2 for frame in app.dataframe)
        requests = state['requests']
        app.checkbox(key='water_basemap').check().run(timeout=30)
        assert not app.exception and len(calls) == 1 and state['requests'] == requests
        assert app.session_state.actions[-1]['action'] == 'Import waterways'
        base_id = app.session_state.water_import_choice
        app.checkbox(key='water_seasonal').check().run(timeout=30)
        app.button(key='import_waterways').click().run(timeout=30)
        seasonal_id = app.session_state.water_import_choice
        assert seasonal_id != base_id
        app.checkbox(key='water_seasonal').uncheck().run(timeout=30)
        app.button(key='import_waterways').click().run(timeout=30)
        assert not app.exception and app.session_state.water_import_choice == base_id
        # Reusing an older base snapshot must not keep previewing the newer seasonal one.
        assert len(latest_water_import(test_engine, app.session_state.water_import_choice)['sources']) == 2
