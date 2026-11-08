import json

import pytest
from shapely import from_wkt

from src.config import ROOT, load_study_area
from src.contracts.spatial import validate_records


def validate(rows, entity='wells', crs='EPSG:4326'):
    return validate_records(rows, entity, crs, load_study_area())


def well(**changes):
    return {'source_well_id': 'SYNTHETIC', 'geometry': {'type':'Point','coordinates':[-114,53.5]}, **changes}


@pytest.mark.parametrize('crs', [None, '', 'EPSG:99999999', 'EPSG:4978'])
def test_missing_or_unsupported_crs_fails_batch(crs):
    with pytest.raises(ValueError):
        validate([well()], crs=crs)


def test_synthetic_fixture_has_exact_accepted_and_quarantine_counts():
    fixture = json.loads((ROOT / 'tests/fixtures/demo.json').read_text())
    wells = validate(fixture['wells'], crs=fixture['crs'])
    features = validate(fixture['features'], entity='features', crs=fixture['crs'])
    assert len(wells.accepted) == 2 and len(wells.rejected) == 5
    assert len(features.accepted) == 2 and len(features.rejected) == 1
    assert [r['reason_code'] for r in wells.rejected] == [
        'duplicate_id', 'duplicate_id', 'missing_id', 'missing_geometry', 'outside_study_area']
    assert features.rejected[0]['reason_code'] == 'invalid_geometry'


def test_duplicate_ids_quarantine_all_occurrences_after_whitespace_normalization():
    batch = validate([well(source_well_id=' ID '), well(source_well_id='ID')])
    assert not batch.accepted
    assert [r['reason_code'] for r in batch.rejected] == ['duplicate_id', 'duplicate_id']


@pytest.mark.parametrize('row,code', [
    (well(source_well_id=None), 'missing_id'),
    (well(geometry=None), 'missing_geometry'),
    (well(geometry={'type':'Point','coordinates':[0,0]}), 'outside_study_area'),
    (well(geometry={'type':'Point','coordinates':[200,100]}), 'invalid_coordinates'),
    (well(geometry={'type':'Point','coordinates':[1,2,3,4]}), 'malformed_geometry'),
    (well(geometry={'type':'LineString','coordinates':[[-114,53],[-114,54]]}), 'geometry_type'),
    (well(licensee_name=42), 'invalid_field_type'),
    ('not an object', 'invalid_record'),
])
def test_invalid_source_rows_have_explicit_reasons(row, code):
    batch = validate([row])
    assert not batch.accepted
    assert batch.rejected[0]['reason_code'] == code
    assert batch.rejected[0]['record_reference'] == 'wells/0'


def test_projection_optional_fields_and_company_labels():
    batch = validate([well(licensee_name=' Synthetic   Company A ')])
    row = batch.accepted[0]
    assert row['licensee_name'] == ' Synthetic   Company A '
    assert row['licensee_search'] == 'synthetic company a'
    assert row['lsd_text'] is None and row['operator_name_if_verified'] is None
    projected = from_wkt(row['geometry_wkt'])
    assert projected.x != -114 and projected.is_valid


@pytest.mark.parametrize('category', [None, ['water']])
def test_malformed_feature_category_is_quarantined(category):
    batch = validate([{'source_feature_id':'SYNTHETIC-FEATURE', 'category':category,
                       'geometry':{'type':'LineString','coordinates':[[-114,53],[-114,54]]}}],
                     entity='features')
    assert not batch.accepted
    assert batch.rejected[0]['reason_code'] == 'invalid_category'
