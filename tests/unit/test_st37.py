import csv
import json
from datetime import date
from pathlib import Path

import pytest

from src.config import load_study_area, ROOT
from src.sources.st37 import FIELDS, checksum, parse_date, prepare_st37
from tests.st37_helpers import synthetic_row, write_workbook


def area():
    return load_study_area(ROOT / 'config/study_area.live.yml')


def records(report, name):
    with Path(report['artifacts'][name]['path']).open(encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))


def test_full_inventory_pilot_and_rejects_reconcile_without_inventing_ids_or_crs(tmp_path):
    path = write_workbook(tmp_path / 'source.xlsx', [
        synthetic_row('0000001'), synthetic_row('0000002', SH_Actual_Longitude=-114.5),
        synthetic_row('0000003'), synthetic_row('0000003', SH_Actual_Longitude=-114.5),
        synthetic_row('0000004', SH_Actual_Longitude=None), synthetic_row(5),
        synthetic_row('0000006', Spud_Date='20010230'),
        synthetic_row('0000007', Licensee='=1+1'),
    ])
    original = checksum(path)
    report = prepare_st37(path, area(), tmp_path / 'output')
    assert (report['source_rows'], report['accepted_rows'], report['quarantined_rows'], report['pilot_rows']) == (8, 2, 6, 1)
    assert report['duplicate_licence_count'] == 1
    assert report['quarantine_reason_counts']['duplicate_licence'] == 2
    assert report['coordinate_crs'] is None
    assert report['source']['downloaded_at'] is None
    assert report['source']['release_date'] is None
    assert checksum(path) == original
    assert list(records(report, 'pilot')[0]) == list(FIELDS)
    assert records(report, 'pilot')[0]['Well_Licence_Number'] == '0000001'
    inventory = records(report, 'inventory')
    assert len(inventory) == 8
    assert [r['source_row'] for r in inventory] == [str(i) for i in range(2, 10)]
    errors = [json.loads(row['validation_errors']) for row in inventory]
    assert 'duplicate_licence' in errors[2] and 'duplicate_licence' in errors[3]
    assert 'nontext_licence' in errors[5]
    assert report == prepare_st37(path, area(), tmp_path / 'output')
    Path(report['artifacts']['pilot']['path']).write_text('corrupt')
    with pytest.raises(ValueError, match='corrupt'):
        prepare_st37(path, area(), tmp_path / 'output')


def test_input_schema_mismatch_is_not_treated_as_empty_data(tmp_path):
    for kwargs in ({'headers': (*FIELDS[:-1], 'Unknown_Field')}, {'sheet': 'Bottom_Holes'}):
        path = write_workbook(tmp_path / 'source.xlsx', [synthetic_row()], **kwargs)
        with pytest.raises(ValueError, match='headers|worksheet'):
            prepare_st37(path, area(), tmp_path / 'output')
    assert not list((tmp_path / 'output').iterdir())


def test_record_caps_fail_without_truncating_or_replacing_previous_output(tmp_path):
    path = write_workbook(tmp_path / 'source.xlsx', [synthetic_row('0000001'), synthetic_row('0000002')])
    report = prepare_st37(path, area(), tmp_path / 'output')
    for kwargs, error in (({'max_rows': 1}, 'row limit'), ({'max_pilot_records': 1}, 'pilot exceeds')):
        with pytest.raises(ValueError, match=error):
            prepare_st37(path, area(), tmp_path / 'output', **kwargs)
    assert [p.name for p in (tmp_path / 'output').iterdir()] == [report['identity']]
    assert prepare_st37(path, area(), tmp_path / 'output') == report


def test_missing_and_nonfinite_locations_and_bad_dates_are_retained_as_rejects(tmp_path):
    path = write_workbook(tmp_path / 'source.xlsx', [
        synthetic_row('', SH_Actual_Latitude='NaN'),
        synthetic_row('0000001', SH_Actual_Longitude=0, Ground_Elevation='unknown'),
    ])
    report = prepare_st37(path, area(), tmp_path / 'output')
    assert report['accepted_rows'] == report['pilot_rows'] == 0
    assert report['quarantined_rows'] == 2
    assert len(records(report, 'quarantine')) == 2
    assert records(report, 'quarantine')[0]['SH_Actual_Latitude'] == 'NaN'
    assert parse_date('02/29/2024').isoformat() == '2024-02-29'
    assert parse_date('19490528').isoformat() == '1949-05-28'
    assert parse_date('') is None
    with pytest.raises(ValueError):
        parse_date('02/29/2023')


def test_changing_original_aborts_publication(tmp_path, monkeypatch):
    from src.sources import st37
    path = write_workbook(tmp_path / 'source.xlsx', [synthetic_row()])
    original_checksum = st37.checksum
    calls = 0

    def changing_checksum(file):
        nonlocal calls
        if Path(file) == path:
            calls += 1
            return 'a' * 64 if calls == 1 else 'b' * 64
        return original_checksum(file)

    monkeypatch.setattr(st37, 'checksum', changing_checksum)
    with pytest.raises(ValueError, match='changed during'):
        prepare_st37(path, area(), tmp_path / 'output')
    assert not list((tmp_path / 'output').iterdir())


def test_future_and_possible_placeholder_dates_are_flagged_without_altering_source(tmp_path):
    path = write_workbook(tmp_path / 'source.xlsx', [
        synthetic_row('0000001', Licence_Status_Date='04/04/2030'),
        synthetic_row('0000002', Licence_Status_Date='01/01/1900'),
    ])
    report = prepare_st37(path, area(), tmp_path / 'output', as_of=date(2026, 11, 10))
    assert report['accepted_rows'] == report['warning_rows'] == 2
    assert report['quarantined_rows'] == 0
    assert report['warning_reason_counts'] == {'future_date:Licence_Status_Date': 1,
                                              'possible_placeholder_date:Licence_Status_Date': 1}
    assert records(report, 'warnings')[0]['Licence_Status_Date'] == '04/04/2030'
    later = prepare_st37(path, area(), tmp_path / 'output', as_of=date(2031, 1, 1))
    assert later['identity'] != report['identity'] and later['warning_rows'] == 1
