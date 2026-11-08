import pytest

from src.spatial.classification import classify_distance, compare_selections, summarize_wells


@pytest.mark.parametrize('distance,band,flags', [
    (0,'within_50m',[True,True,True,True]),
    (50,'within_50m',[True,True,True,True]),
    (50.01,'within_100m',[False,True,True,True]),
    (100,'within_100m',[False,True,True,True]),
    (100.01,'within_250m',[False,False,True,True]),
    (250,'within_250m',[False,False,True,True]),
    (250.01,'within_500m',[False,False,False,True]),
    (500,'within_500m',[False,False,False,True]),
    (500.01,'none_within_500m',[False,False,False,False]),
    (None,'none_within_500m',[False,False,False,False]),
])
def test_inclusive_bands_and_cumulative_flags(distance, band, flags):
    result = classify_distance(distance)
    assert result['band'] == band
    assert [result[f'within_{t}'] for t in (50,100,250,500)] == flags


@pytest.mark.parametrize('distance', [-1,float('nan'),float('inf'),True])
def test_invalid_distance_is_rejected(distance):
    with pytest.raises(ValueError):
        classify_distance(distance)


def row(category='water', distance=100, coverage='complete'):
    return {'well_pk':1,'source_well_id':'SYNTHETIC','category':category,
            'distance_m':distance,'coverage_status':coverage}


def test_category_selection_recomputes_minimum_and_threshold():
    rows = [row(),row('protected_area',0)]
    assert summarize_wells(rows,['water','protected_area'])[0]['band'] == 'within_50m'
    assert summarize_wells(rows,['water'],50)[0]['matches_threshold'] is False
    assert summarize_wells(rows,['protected_area'],50)[0]['matches_threshold'] is True
    assert compare_selections(summarize_wells(rows,['water']),summarize_wells(rows,['protected_area']))['changed_well_ids'] == ['SYNTHETIC']


def test_unknown_category_cannot_produce_false_negative_or_exact_overall_band():
    rows = [row(),row('protected_area',None,'incomplete')]
    result = summarize_wells(rows,['water','protected_area'],50)[0]
    assert result['band'] == 'unknown' and result['distance_m'] is None
    assert result['observed_min_distance_m'] == 100
    assert result['matches_threshold'] is None
    assert result['within_100'] is True  # A verified positive remains observable.


def test_missing_coverage_and_empty_selection_retain_wells_as_unknown():
    rows = [row(distance=None)]
    assert summarize_wells(rows,['water'])[0]['matches_threshold'] is False
    assert summarize_wells(rows,['esa'])[0]['matches_threshold'] is None
    assert summarize_wells(rows,[])[0]['band'] == 'no_categories_selected'


def test_invalid_category_and_threshold_cannot_silently_change_selection():
    with pytest.raises(ValueError):
        summarize_wells([row()],['invented'])
    with pytest.raises(ValueError):
        summarize_wells([row()],['water'],75)
