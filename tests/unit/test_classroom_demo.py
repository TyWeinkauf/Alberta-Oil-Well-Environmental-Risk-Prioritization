"""Classroom package, metre-analysis and no-DB app regression checks."""
import csv
import json
from pathlib import Path

import pytest
from shapely.geometry import shape
from streamlit.testing.v1 import AppTest

from src.config import ROOT, load_study_area
from src.demo.data import decode_package, dashboard_for, prepare_package
from src.demo.regions import REGION_IDS, load_regions
from src.demo.spatial import analyze, feature_geometry
from src.sources.st37 import checksum, prepare_st37
from src.spatial.classification import summarize_wells
from tests.st37_helpers import synthetic_row, write_workbook


@pytest.fixture
def source_inventory(tmp_path):
    rows = [
        synthetic_row(f'{index:07}', SH_Actual_Latitude=latitude, SH_Actual_Longitude=longitude,
                      Licensee=company)
        for index, (latitude, longitude, company) in enumerate([
            (52.22, -113.88, 'Example A'), (52.26, -113.80, 'Example B'),
            (52.30, -113.78, 'Example A'), (53.25, -115.0, 'Example B'),
            (53.29, -114.99, 'Example A'), (52.48, -114.40, 'Outside both regions'),
            (53.25, -115.0, 'Quarantined'),
        ], start=1)
    ]
    rows[-1]['Licence_Status_Date'] = 'bad date'
    workbook = write_workbook(tmp_path / 'fixture.xlsx', rows)
    report = prepare_st37(workbook, load_study_area(), tmp_path / 'inventory')
    assert report['accepted_rows'] == 6
    inventory = Path(report['artifacts']['inventory']['path'])
    return workbook, inventory, inventory.with_name('report.json')


def test_raw_preview_preserves_rows_and_previous_output(source_inventory, tmp_path, monkeypatch):
    _, inventory, report = source_inventory
    original_hashes = [checksum(path) for path in source_inventory]
    config = load_regions()
    config.sample_limit = 2
    output = tmp_path / 'preview.json'
    package = prepare_package(report, config, output)
    previous = output.read_bytes()
    assert prepare_package(report, config, output)['package_id'] == package['package_id']
    assert output.read_bytes() == previous
    assert package['manifest']['coordinate_reference'] is None
    assert [package['regions'][key]['candidate_count'] for key in REGION_IDS] == [3, 2]
    with inventory.open(newline='', encoding='utf-8') as stream:
        original_rows = {int(row['source_row']): row for row in csv.DictReader(stream)}
    for group in package['regions'].values():
        assert len(group['wells']) == 2 and not group['features']
        for row in group['wells']:
            assert all(value == original_rows[row['source_row']][key] for key, value in row['raw'].items())
    assert [checksum(path) for path in source_inventory] == original_hashes
    assert 'path' not in package['manifest']['source']
    with pytest.raises(ValueError, match='both'):
        prepare_package(report, config, output, coordinate_crs='EPSG:4269')
    with pytest.raises(ValueError, match='geographic'):
        prepare_package(report, config, output, coordinate_crs='EPSG:3400', crs_evidence='Wrong units')
    with pytest.raises(ValueError, match='Choose a separate'):
        prepare_package(report, config, report)
    with pytest.raises(ValueError, match='checksum'):
        decode_package(previous.replace(b'Example A', b'Example X', 1))
    assert output.read_bytes() == previous

    def fail_publish(*args):
        raise PermissionError('Injected write failure')

    monkeypatch.setattr('src.demo.data.os.replace', fail_publish)
    with pytest.raises(PermissionError):
        prepare_package(report, config, output)
    assert output.read_bytes() == previous
    assert list(tmp_path.glob('.classroom-*')) == []


@pytest.fixture
def projected_package(source_inventory, tmp_path):
    _, _, report = source_inventory
    output = tmp_path / 'known-crs.json'
    package = prepare_package(report, load_regions(), output,
                              coordinate_crs='EPSG:4326', crs_evidence='Declared datum of synthetic test fixture')
    return package, output


def test_standalone_and_both_regions_agree(projected_package):
    package, output = projected_package
    data = decode_package(output.read_bytes())
    both = dashboard_for(data, REGION_IDS)
    assert len(both['proximity']) == 5 * len(both['wells'])
    for key in REGION_IDS:
        alone = dashboard_for(data, (key,))
        ids = {row['well_pk'] for row in alone['wells']}
        assert alone['proximity'] == [row for row in both['proximity'] if row['well_pk'] in ids]
        assert len(alone['features']) == 6
        assert {row['feature_type'] for row in alone['features']} == {
            'water', 'wetland', 'protected_area', 'critical_habitat', 'esa',
        }
        assert all(feature_geometry(feature).is_valid for feature in package['regions'][key]['features'])
    assert package['regions']['red_deer']['generator_seed'] != package['regions']['drayton_valley']['generator_seed']


def test_metre_boundaries_ties_and_unknown_coverage():
    fixture = json.loads((ROOT / 'tests/fixtures/spatial_boundaries.json').read_text(encoding='utf-8'))
    wells = [{'source_row': index, 'raw': {'Well_Licence_Number': row['source_well_id']}}
             for index, row in enumerate(fixture['wells'])]
    points = {index: shape(row['geometry']) for index, row in enumerate(fixture['wells'])}
    features = [
        {'source_feature_id': row['source_feature_id'], 'feature_type': row['category'], 'geometry_3400': row['geometry']}
        for row in fixture['features']
    ]
    results = analyze(wells, points, features, {'water': 'complete', 'protected_area': 'complete'})
    water = [row for row in results if row['category'] == 'water'][:6]
    assert [row['distance_m'] for row in water] == [0, 50, 100, 250, 500, None]
    assert [row['nearest_feature_id'] for row in water] == ['TIE-A'] * 5 + [None]
    assert [row['band'] for row in water] == [
        'within_50m', 'within_50m', 'within_100m', 'within_250m', 'within_500m', 'none_within_500m',
    ]
    interior = next(row for row in results if row['source_well_id'] == 'INSIDE-POLYGON'
                    and row['category'] == 'protected_area')
    assert interior['distance_m'] == 0
    summary = summarize_wells(results, ['water', 'critical_habitat'])
    by_licence = {row['source_well_id']: row for row in summary}
    assert by_licence['BOUNDARY-0']['matches_threshold'] is True
    assert by_licence['BOUNDARY-0']['band'] == 'unknown'
    assert by_licence['BOUNDARY-500.01']['matches_threshold'] is None


def test_streamlit_modes_without_database(source_inventory, projected_package, tmp_path, monkeypatch):
    _, output = projected_package
    _, _, report = source_inventory
    preview = tmp_path / 'preview.json'
    prepare_package(report, load_regions(), preview)
    monkeypatch.setenv('CLASSROOM_DEMO_PATH', str(preview))

    def fail_database_preflight():
        pytest.fail('The classroom path reached database preflight')

    with monkeypatch.context() as patch:
        patch.setattr('src.config.database_url', fail_database_preflight)
        app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=20).run()
        assert not app.exception and app.metric[2].value == '3'
        assert any('coordinate datum is pending' in alert.value for alert in app.info)
        assert not app.get('component_instance')
        monkeypatch.setenv('CLASSROOM_DEMO_PATH', str(output))
        app.run()
        assert not app.exception and app.metric[2].value == '3'
        assert any('synthetic environmental features' in alert.value for alert in app.info)
        app.selectbox(key='classroom_inspect').select(2).run()
        assert not app.exception and any('100 m buffer' in caption.value for caption in app.caption)
        app.radio(key='classroom_region').set_value('both').run()
        assert not app.exception and app.metric[2].value == '5'
        assert app.selectbox(key='classroom_inspect').value is None
        app.text_input(key='classroom_licence').input('0000004').run()
        assert not app.exception and app.metric[2].value == '1'

    def missing_database_url():
        raise ValueError('PostGIS deliberately unavailable in the classroom test')

    monkeypatch.setattr('src.config.database_url', missing_database_url)
    app.selectbox(key='dataset_mode').select('PostGIS workflows').run()
    assert not app.exception and any('DATABASE_URL' in alert.value for alert in app.error)
    app.selectbox(key='dataset_mode').select('Classroom demo').run()
    assert not app.exception and app.text_input(key='classroom_licence').value == ''
    assert app.selectbox(key='classroom_threshold').value == 100
