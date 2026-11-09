"""Synthetic files exercise local acquisition; no publisher schema is implied."""
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.config import Source, load_source_catalog, load_study_area
from src.contracts.spatial import validate_records
from src.sources.files import acquire_file
from src.sources.http import HttpCache
from src.sources.local import acquire_snapshot


def source(path, **kwargs):
    return Source.model_validate(dict(key='synthetic-local',kind='file',local_path=path,metadata_url='https://example.invalid/metadata',
                  downloaded_at=datetime(2026,11,8,tzinfo=timezone.utc),publisher='Synthetic test publisher')|kwargs)


def test_local_snapshot_is_immutable_rechecks_bytes_and_retains_provenance(tmp_path,monkeypatch):
    path=tmp_path/'input.csv';path.write_bytes(b'first')
    cache=HttpCache(tmp_path/'cache')
    monkeypatch.setattr(cache.session,'get',lambda *a,**kw:pytest.fail('Local files must not request a URL'))
    item=source(path)
    first=acquire_snapshot(item,cache)
    assert acquire_snapshot(item,cache)==first
    assert first.metadata['url']=='https://example.invalid/metadata'
    assert first.metadata['downloaded_at']=='2026-11-08T00:00:00+00:00'
    path.write_bytes(b'other')  # Same size: mtime/size are not accepted as byte identity.
    second=acquire_snapshot(item,cache)
    assert second.path!=first.path and first.path.read_bytes()==b'first'
    second.path.write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='blob is corrupt'):
        acquire_snapshot(item,cache)


def test_local_caps_missing_file_and_directory_are_rejected(tmp_path):
    path=tmp_path/'input';path.write_bytes(b'12345')
    with pytest.raises(ValueError,match='byte limit'):
        acquire_snapshot(source(path),HttpCache(tmp_path/'cache',max_bytes=4))
    with pytest.raises(ValueError,match='total transfer budget'):
        acquire_snapshot(source(path),HttpCache(tmp_path/'cache',max_bytes=10,max_total_bytes=4))
    for path in [tmp_path, tmp_path/'missing']:
        with pytest.raises(ValueError,match='regular file'):
            acquire_snapshot(source(path),HttpCache(tmp_path/'cache'))
    assert not list((tmp_path/'cache').glob('tmp*'))


def test_local_config_provenance_and_catalogue_relative_paths(tmp_path):
    args=source(tmp_path/'input',native_crs='EPSG:3400',field_mapping={'source_well_id':'ID'},license_note='Synthetic').model_dump()
    for field in ['publisher','downloaded_at','metadata_url']:
        with pytest.raises(ValidationError,match='Local input requires'):
            Source.model_validate(args|{field:None,'enabled':True,'verified':True})
    with pytest.raises(ValidationError,match='timezone'):
        source(tmp_path/'input',**{'downloaded_at':'2026-11-08T00:00:00'})


def test_catalogue_relative_path_is_independent_of_working_directory(tmp_path,monkeypatch):
    catalog=tmp_path/'catalog.yml'
    catalog.write_text('sources:\n  - key: local\n    kind: file\n    local_path: downloads/wells.geojson\n')
    monkeypatch.chdir('/')
    assert load_source_catalog(catalog).sources[0].local_path==tmp_path/'downloads/wells.geojson'


def test_coordinate_csv_retains_string_ids_and_quarantines_bad_coordinates(tmp_path):
    path=tmp_path/'wells.csv'
    path.write_text('ID,COMPANY,X,Y\n000123,Synthetic,500000,5900000\n000124,Synthetic,bad,5900000\n000125,Synthetic,0,0\n')
    item=source(path,native_crs='EPSG:3400',csv_x_field='X',csv_y_field='Y',
                field_mapping={'source_well_id':'ID','licensee_name':'COMPANY'})
    data=acquire_file(item,load_study_area(),HttpCache(tmp_path/'cache'))
    batch=validate_records(data.records,'wells',data.records_crs,load_study_area())
    assert [r['source_well_id'] for r in batch.accepted]==['000123']
    assert len(batch.rejected)==2 and any(r['reason_code']=='outside_study_area' for r in batch.rejected)
    with pytest.raises(ValueError,match='record limit'):
        acquire_file(item,load_study_area(),HttpCache(tmp_path/'cache'),max_records=2)
    path.write_text('ID,COMPANY,X,Y\n1,2,3\n')
    with pytest.raises(ValueError,match='Malformed'):
        acquire_file(item,load_study_area(),HttpCache(tmp_path/'cache'))
