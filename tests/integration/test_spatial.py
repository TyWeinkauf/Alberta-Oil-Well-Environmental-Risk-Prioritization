import json
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from src.config import ROOT
from src.db.demo import seed_demo
from src.db.migrations import migrate
from src.spatial.classification import compare_selections, summarize_wells
from src.spatial.engine import Coverage, analyze_run, read_results

pytestmark = pytest.mark.integration
FIXTURE = ROOT / 'tests/fixtures/spatial_boundaries.json'


@pytest.fixture
def spatial_seed(test_engine, tmp_path):
    migrate(test_engine)
    report = seed_demo(test_engine,FIXTURE,raw_root=tmp_path/'raw',output_root=tmp_path/'runs')
    return report


def test_postgis_known_distances_boundaries_and_nearest_tie(test_engine, spatial_seed):
    rows = analyze_run(test_engine,spatial_seed['run_id'])
    assert len(rows) == 8*5
    water = {r['source_well_id']:r for r in rows if r['category']=='water'}
    for distance in [0,50,100,250,500,500.01]:
        row = water[f'BOUNDARY-{distance:g}']
        if distance <= 500:
            assert row['distance_m'] == pytest.approx(distance,abs=1e-8)
            assert row['nearest_feature_id'] == 'TIE-A'  # Stable ID breaks equal-distance ties.
            assert row['result_state'] == 'matched'
        else:
            assert row['distance_m'] is None and row['nearest_feature_id'] is None
            assert row['result_state'] == 'no_feature_within_500m'
        assert [row[f'within_{t}'] for t in (50,100,250,500)] == [distance<=t for t in (50,100,250,500)]
    # Distance to the actual line is 0; distance to its centroid would be 900 m.
    assert water['NEAR-LINE-END']['distance_m'] == 0
    park = next(r for r in rows if r['category']=='protected_area' and r['source_well_id']=='INSIDE-POLYGON')
    assert park['distance_m'] == 0  # Interior, not centroid or polygon boundary distance.


def test_category_and_threshold_sensitivity_identifies_changed_ids(test_engine, spatial_seed):
    rows = analyze_run(test_engine,spatial_seed['run_id'])
    water = summarize_wells(rows,['water'],100)
    combined = summarize_wells(rows,['water','protected_area'],100)
    water_by_id = {r['source_well_id']:r for r in water}
    combined_by_id = {r['source_well_id']:r for r in combined}
    assert water_by_id['BOUNDARY-250']['matches_threshold'] is False
    assert combined_by_id['BOUNDARY-250']['matches_threshold'] is True
    assert combined_by_id['BOUNDARY-100']['distance_m'] == 0
    sensitivity = compare_selections(summarize_wells(rows,['water'],500),summarize_wells(rows,['water'],50))
    assert sensitivity['changed_well_ids'] == ['BOUNDARY-100','BOUNDARY-250','BOUNDARY-500','INSIDE-POLYGON']
    assert sensitivity['baseline_matched'] == 7 and sensitivity['changed_matched'] == 3


def test_no_nearby_unavailable_and_incomplete_are_distinct(test_engine, spatial_seed):
    rows = analyze_run(test_engine,spatial_seed['run_id'],
                       {'protected_area':Coverage(status='incomplete',note='Synthetic missing source coverage')})
    outside = next(r for r in rows if r['category']=='water' and r['source_well_id']=='BOUNDARY-500.01')
    assert outside['result_state'] == 'no_feature_within_500m' and outside['within_500'] is False
    incomplete = next(r for r in rows if r['category']=='protected_area')
    unavailable = next(r for r in rows if r['category']=='critical_habitat')
    assert incomplete['result_state'] == 'incomplete' and incomplete['within_500'] is None
    assert unavailable['result_state'] == 'unavailable' and unavailable['within_500'] is None


def test_run_isolation_excludes_other_runs_features(test_engine, spatial_seed, tmp_path):
    fixture = json.loads(FIXTURE.read_text())
    for feature in fixture['features'][:2]:
        feature['geometry']['coordinates'] = [[500500.01,5899000],[500500.01,5901000]]
    other = tmp_path/'other.json'
    other.write_text(json.dumps(fixture))
    foreign = seed_demo(test_engine,other,raw_root=tmp_path/'raw',output_root=tmp_path/'runs')
    analyze_run(test_engine,foreign['run_id'])
    rows = analyze_run(test_engine,spatial_seed['run_id'])
    result = next(r for r in rows if r['category']=='water' and r['source_well_id']=='BOUNDARY-500.01')
    assert result['distance_m'] is None  # A foreign run's water is exactly here.
    assert len(rows) == 40


def test_analysis_and_seed_reruns_preserve_counts_and_results(test_engine, spatial_seed, tmp_path):
    first = analyze_run(test_engine,spatial_seed['run_id'])
    assert analyze_run(test_engine,spatial_seed['run_id']) == first
    again = seed_demo(test_engine,FIXTURE,raw_root=tmp_path/'raw',output_root=tmp_path/'runs')
    assert again['counts']['well_proximity'] == 40
    assert read_results(test_engine,spatial_seed['run_id']) == first


def test_failed_analysis_preserves_previous_results_and_coverage(test_engine, spatial_seed):
    first = analyze_run(test_engine,spatial_seed['run_id'])
    with test_engine.begin() as conn:
        conn.exec_driver_sql('''CREATE FUNCTION screening.reject_analysis() RETURNS trigger LANGUAGE plpgsql AS
            $$ BEGIN RAISE EXCEPTION 'synthetic spatial failure'; END; $$;
            CREATE TRIGGER reject_analysis BEFORE INSERT ON screening.well_proximity
            FOR EACH ROW EXECUTE FUNCTION screening.reject_analysis();''')
    with pytest.raises(DBAPIError,match='synthetic spatial failure'):
        analyze_run(test_engine,spatial_seed['run_id'],{'water':Coverage(status='incomplete',note='Incomplete test')})
    assert read_results(test_engine,spatial_seed['run_id']) == first


def test_missing_run_and_unknown_categories_fail_before_writing(test_engine, spatial_seed):
    with pytest.raises(ValueError,match='existing seeded run'):
        analyze_run(test_engine,str(uuid4()))
    with pytest.raises(ValueError,match='Unknown environmental category'):
        analyze_run(test_engine,spatial_seed['run_id'],{'invented':Coverage(status='complete',note='test')})
    assert read_results(test_engine,spatial_seed['run_id']) == []


def test_quarantined_feature_prevents_complete_demo_coverage(test_engine, tmp_path):
    migrate(test_engine)
    report = seed_demo(test_engine,raw_root=tmp_path/'raw',output_root=tmp_path/'runs')
    rows = analyze_run(test_engine,report['run_id'])
    assert all(r['coverage_status']=='incomplete' for r in rows if r['category']=='protected_area')
    assert all(r['coverage_status']=='complete' for r in rows if r['category']=='water')


def test_seed_downgrade_invalidates_older_complete_coverage_results(test_engine, tmp_path):
    migrate(test_engine)
    report = seed_demo(test_engine,raw_root=tmp_path/'raw',output_root=tmp_path/'runs')
    analyze_run(test_engine,report['run_id'],{'protected_area':Coverage(status='complete',note='Older synthetic assumption')})
    again = seed_demo(test_engine,raw_root=tmp_path/'raw',output_root=tmp_path/'runs')
    assert again['counts']['well_proximity'] == 0
    assert read_results(test_engine,report['run_id']) == []


def test_run_configuration_must_match_the_implemented_spatial_method(test_engine, spatial_seed):
    with test_engine.begin() as conn:
        conn.execute(text('''UPDATE screening.pipeline_runs
            SET study_area=jsonb_set(study_area,'{thresholds_m}','[10,20]') WHERE run_id=:run'''),
                     {'run':spatial_seed['run_id']})
    with pytest.raises(ValueError,match='standard'):
        analyze_run(test_engine,spatial_seed['run_id'])
