"""Province inventory, transactional rejection handling and ST37/PostGIS comparison."""
import json
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import text
from streamlit.testing.v1 import AppTest

from src.config import ROOT, load_study_area
from src.db import st37
from src.db.st37 import import_st37
from src.db.waterbodies import (
    compare_st37_waterbodies, latest_province_waterbodies, st37_water_comparisons, waterbody_comparison_summary,
    waterbody_buffer_count, waterbody_map_batch, waterbody_result,
)
from src.demo.data import IMPORTED_WATER_MODE, dashboard_for, prepare_package
from src.demo.hydrography import extract_imported_water
from src.demo.regions import REGION_IDS, load_regions
from src.demo.spatial import WATER_PROVENANCE
from src.sources.http import HttpCache
from src.sources.hydrography import latest_water_import
from src.sources.st37 import prepare_st37
from src.sources.waterbodies import PROVINCE_STREAM_SCOPE, import_province_streams, import_province_waterbodies
from src.ui import waterbody_workflow
from src.ui.model import filtered_wells
from tests.hydro_helpers import hydro_service, water_controls_app
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
        synthetic_row('0000014', SH_Actual_Latitude=53.2525),
        synthetic_row('0000015', SH_Actual_Longitude='invalid'),
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
    assert [row['comparison_id'] for row in st37_water_comparisons(test_engine, well_id)] == [comparison]
    assert st37_water_comparisons(test_engine, UUID(raw['import_id'])) == []
    assert latest_province_waterbodies(test_engine)['comparison_id'] == comparison
    summary = waterbody_comparison_summary(test_engine, comparison)
    assert summary['well_count'] == 3 and summary['within_50'] == 1 and summary['unknown_within_500'] == 1
    match = waterbody_result(test_engine, comparison, '0000012')
    assert match is not None and match['observed_distance_m'] == 0 and match['nearest_source_feature_id'] == '10'
    unmatched = waterbody_result(test_engine, comparison, '0000013')
    assert unmatched is not None and unmatched['result_state'] == 'unknown_incomplete_coverage'
    pages = [waterbody_map_batch(test_engine, comparison, seed=123, offset=index, limit=1) for index in range(3)]
    assert waterbody_map_batch(test_engine, comparison, seed=123, limit=1) == pages[0]
    assert waterbody_map_batch(test_engine, comparison, seed=123, offset=3, limit=1) == ([], [])
    assert sorted(wells[0]['well_licence_number'] for wells, _ in pages) == ['0000012', '0000013', '0000014']
    assert waterbody_buffer_count(test_engine, comparison, 50) == 1
    assert waterbody_buffer_count(test_engine, comparison, 250) == 2
    within_50, _ = waterbody_map_batch(test_engine, comparison, seed=123, max_distance_m=50)
    assert [well['well_licence_number'] for well in within_50] == ['0000012']
    wider, _ = waterbody_map_batch(test_engine, comparison, seed=123, max_distance_m=250)
    assert {well['well_licence_number'] for well in wider} == {'0000012', '0000014'}
    focused, water = waterbody_map_batch(test_engine, comparison, seed=123, licence='0000012')
    assert focused[0]['geometry']['coordinates'] == pytest.approx([-115.0, 53.25])
    assert water[0]['source_feature_id'] == '10'
    assert waterbody_map_batch(test_engine, comparison, seed=123, licence='12') == ([], [])
    excluded = (focused[0]['source_row'],)
    included, _ = waterbody_map_batch(test_engine, comparison, seed=123, excluded_rows=excluded)
    assert {well['well_licence_number'] for well in included} == {'0000013', '0000014'}
    assert waterbody_buffer_count(test_engine, comparison, 50, excluded) == 0
    assert not waterbody_map_batch(test_engine, comparison, seed=123, excluded_rows=excluded, max_distance_m=50)[0]
    assert waterbody_map_batch(test_engine, comparison, seed=123, licence='0000012', excluded_rows=excluded) == ([], [])
    for wells, features in pages:
        point = wells[0]
        assert point['geometry']['type'] == 'Point'
        if point['well_licence_number'] == '0000012':
            assert point['observed_distance_m'] == 0
            assert [feature['source_feature_id'] for feature in features] == ['10']
            assert features[0]['geometry']['type'] == 'Polygon'
        elif point['well_licence_number'] == '0000014':
            assert 100 < point['observed_distance_m'] < 250
        else:
            assert point['observed_distance_m'] is None and features == []
    with pytest.raises(ValueError, match='10,000'):
        waterbody_map_batch(test_engine, comparison, seed=123, limit=10_001)
    with test_engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM screening.pipeline_runs')).scalar_one() == 0
    monkeypatch.setenv('DATABASE_URL', test_engine.url.render_as_string(hide_password=False))
    monkeypatch.setattr(waterbody_workflow, 'WELL_MAP_BATCH_SIZE', 1)
    app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=20)
    app.query_params['dataset_mode'] = 'ST37 well inventory'
    app.run()
    assert not app.exception and any('3 ST37 wells' in element.value for element in app.caption)
    assert app.segmented_control(key='st37_map_threshold').value == 500
    assert app.checkbox(key='st37_map_matches_only').value
    assert app.checkbox(key='st37_inventory_basemap').value
    assert any('Batch 1 of 2 · Showing 1 of 2 wells' in element.value for element in app.caption)
    app.button(key='province_map_next').click().run()
    assert not app.exception and any('Batch 2 of 2 · Showing 1 of 2 wells' in element.value for element in app.caption)
    app.segmented_control(key='st37_map_threshold').set_value(50).run()
    assert any('Batch 1 of 1 · Showing 1 of 1 wells' in element.value for element in app.caption)
    app.checkbox(key='st37_map_matches_only').uncheck().run()
    assert any('Batch 1 of 3 · Showing 1 of 3 wells' in element.value for element in app.caption)
    app.checkbox(key='st37_map_matches_only').check().run()
    app.text_input(key='st37_inventory_licence').input('0000014').run()
    assert not app.exception
    assert any('50 m buffer around selected well 0000014' in element.value for element in app.caption)
    assert any('well_licence_number' in frame.value and frame.value['well_licence_number'].tolist() == ['0000014']
               for frame in app.dataframe)

    audit = tmp_path / 'alberta_boundary.json'
    audit.write_text(json.dumps({'st37_snapshot': str(well_id), 'outside_source_rows': excluded}), encoding='utf-8')
    monkeypatch.setattr(waterbody_workflow, 'ST37_ALBERTA_BOUNDARY_QA', audit)
    app.text_input(key='st37_inventory_licence').input('').run()
    assert not app.exception
    assert any('No observed well matches within 50 m' in element.value for element in app.info)
    app.text_input(key='st37_inventory_licence').input('0000012').run()
    assert not app.exception and any('position falls outside the Alberta boundary' in e.value for e in app.info)
    app.radio(key='st37_inventory_view').set_value('Workbook records').run()
    assert not app.exception
    outside = app.dataframe[0].value.iloc[0]
    assert outside['Well_Licence_Number'] == '0000012'
    assert outside['Boundary review'] == 'Reported position outside Alberta'
    assert outside['Observed water distance (m)'] == 0
    assert outside['Water proximity band'] == '≤50 m'
    app.text_input(key='st37_inventory_licence').input('').run()
    records = app.dataframe[0].value.set_index('Well_Licence_Number')
    assert records.loc['0000013', 'Water proximity band'] == 'No match within 500 m'
    assert records.loc['0000014', 'Water proximity band'] == '>100–250 m'
    band_filter = next(widget for widget in app.multiselect if widget.label == 'Water proximity band')
    band_key = band_filter.key
    assert band_key is not None
    band_filter.set_value(['within_250m']).run()
    assert app.dataframe[0].value['Well_Licence_Number'].tolist() == ['0000014']
    app.text_input(key='st37_inventory_licence').input('0000012').run()
    assert not app.dataframe and any('match the licence and selected filters' in item.value for item in app.info)
    app.text_input(key='st37_inventory_licence').input('').run()
    app.multiselect(key=band_key).set_value(['within_50m', 'none_within_500m']).run()
    assert app.dataframe[0].value['Well_Licence_Number'].tolist() == ['0000012', '0000013']
    app.multiselect(key=band_key).set_value(['unavailable']).run()
    assert app.dataframe[0].value['Well_Licence_Number'].tolist() == ['0000015']


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
        app = AppTest.from_function(water_controls_app, default_timeout=20)
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
        evidence_path = tmp_path / 'datum.json'
        evidence_path.write_text(json.dumps({
            'workbook_sha256': relocated['source']['sha256'],
            'geodatabase': {'geometry_base_crs': 'EPSG:4326'},
            'crs_evidence': 'Declared WGS84 for the test workbook',
            'release_date': '2026-11-03',
        }), encoding='utf-8')
        monkeypatch.setattr(st37, 'ST37_DATUM_EVIDENCE', evidence_path)
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
            declaration = conn.execute(text('''SELECT coordinate_crs, crs_evidence, release_date::text
                FROM screening.st37_imports WHERE import_id=:id'''), {'id': well_id}).one()
            assert declaration == ('EPSG:4326', 'Declared WGS84 for the test workbook', '2026-11-03')
            assert conn.execute(text('SELECT count(*) FROM screening.water_imports')).scalar_one() == 1
            assert conn.execute(text('SELECT count(*) FROM screening.waterbody_comparisons')).scalar_one() == 1


def test_app_can_import_and_compare_province_streams(test_engine, tmp_path, monkeypatch):
    workbook = write_workbook(tmp_path / 'fixture.xlsx', [synthetic_row('0000012'),
        synthetic_row('0000013', SH_Actual_Latitude=52.25, SH_Actual_Longitude=-113.81)])
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
        app = AppTest.from_function(water_controls_app, default_timeout=20)
        app.run()
        requests = simulator['requests']
        app.checkbox(key='province_water_comparison').check().run()
        assert not app.exception and simulator['requests'] == requests
        app.button(key='import_province_streams').click().run()
        assert not app.exception and not app.error
        streams_id = app.selectbox(key='province_water_snapshot').value
        assert isinstance(streams_id, UUID)
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
        assert row is not None and row['nearest_source_feature_id'] == '10'
        assert 0 < row['observed_distance_m'] < 50
        regions = load_regions()
        output = tmp_path / 'classroom-with-water.json'
        hydro = extract_imported_water(test_engine, regions, UUID(water['import_id']), streams_id)
        package = prepare_package(report, regions, output, coordinate_crs='EPSG:4326',
                                  crs_evidence='Declared WGS84 for test workbook', hydrography=hydro)
        assert package['manifest']['mode'] == IMPORTED_WATER_MODE
        local_water = [f for f in package['regions']['drayton_valley']['features'] if f['feature_type'] == 'water']
        assert {f['subtype'] for f in local_water} == {'stream', 'waterbody'}
        assert all(f['provenance'] == WATER_PROVENANCE for f in local_water)
        distances = {r['source_well_id']: r for r in filtered_wells(dashboard_for(package, REGION_IDS), ['water'], 50)}
        assert distances['0000012']['observed_min_distance_m'] == 0
        assert distances['0000012']['matches_threshold'] is True
        assert distances['0000013']['matches_threshold'] is None
        monkeypatch.setenv('CLASSROOM_DEMO_PATH', str(output))
        classroom = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=20).run()
        assert not classroom.exception and not classroom.error
        assert any('imported waterways' in heading.value for heading in classroom.subheader)
        classroom.radio(key='classroom_region').set_value('both').run()
        assert classroom.segmented_control(key='classroom_threshold').value == 500
        assert classroom.checkbox(key='classroom_matches_only').value
        assert classroom.metric[2].value == '1' and classroom.metric[3].value == '1'
        classroom.segmented_control(key='classroom_threshold').set_value(50).run()
        assert not classroom.exception and classroom.metric[2].value == '1'
        classroom.checkbox(key='classroom_matches_only').uncheck().run()
        assert classroom.metric[2].value == '2' and classroom.segmented_control(key='classroom_threshold').value == 50
        classroom.radio(key='classroom_region').set_value('red_deer').run()
        assert classroom.metric[2].value == '0'
        assert any('No observed well matches within 500 m' in alert.value for alert in classroom.info)
        assert any('unknown water proximity' in alert.value for alert in classroom.warning)
        requests = simulator['requests']
        app.run()
        assert simulator['requests'] == requests
        app.selectbox(key='province_water_snapshot').select(UUID(water['import_id'])).run()
        assert not app.exception and app.button(key='compare_waterbodies').label == 'Run waterbody comparison'
        app.button(key='compare_waterbodies').click().run()
        inventory = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=20)
        inventory.query_params['dataset_mode'] = 'ST37 well inventory'
        inventory.run()
        inventory.radio(key='st37_inventory_view').set_value('Workbook records').run()
        assert not inventory.exception and not inventory.error
        table = inventory.dataframe[0].value.set_index('Well_Licence_Number')
        assert 'Intersects water' not in table.columns
        assert table.loc['0000012', 'Observed water distance (m)'] == 0
        assert table.loc['0000012', 'Water proximity band'] == '≤50 m'
