"""Synthetic GIS originals test bounded preparation, scope and lineage."""
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point

from src.config import Source, load_study_area
from src.sources.extract import inspect_original, parent_fingerprint, prepare_extract
from src.sources.files import acquire_file
from src.sources.http import HttpCache
from src.spatial.extent import study_geometry


def source(path,**kwargs):
    return Source.model_validate(dict(key='aer_wells',kind='file',local_path=path,
        publisher='Synthetic test publisher',metadata_url='https://example.invalid/synthetic',
        downloaded_at=datetime(2026,11,8,tzinfo=timezone.utc),license_note='Project-authored fixture only',
        native_crs='EPSG:3400',field_mapping={'source_well_id':'ID','licensee_name':'COMPANY'},
        coverage_note='Closed synthetic region plus margin')|kwargs)


@pytest.fixture
def area():
    return load_study_area().model_copy(update={'mode':'live'})


@pytest.fixture(params=['gpkg','gdb','gdbzip'])
def original(tmp_path,request):
    driver='GPKG' if request.param=='gpkg' else 'OpenFileGDB'
    path=tmp_path/('original.gpkg' if driver=='GPKG' else 'original.gdb')
    gpd.GeoDataFrame({'ID':['000123','far'],'COMPANY':['Synthetic','Other'],'UNNEEDED':['drop','drop']},
        geometry=[Point(500000,5900000),Point(0,0)],crs=3400).to_file(path,driver=driver,layer='surface')
    if request.param=='gdbzip':
        archive=tmp_path/'original.zip'
        with zipfile.ZipFile(archive,'w') as target:
            for item in path.rglob('*'):
                if item.is_file():target.write(item,item.relative_to(tmp_path))
        return archive
    return path


def prepared_source(report):
    return Source.model_validate(report['catalogue_entry']|{'local_path':report['package_path']})


def test_original_formats_prepare_small_immutable_packages_and_native_geometry(original,tmp_path,area):
    item=source(original,file_layer='surface')
    before=parent_fingerprint(original)
    report=prepare_extract(item,area,tmp_path/'extracts')
    assert prepare_extract(item,area,tmp_path/'extracts')==report
    assert parent_fingerprint(original)==before
    second_root=prepare_extract(item,area,tmp_path/'other-extracts')
    assert second_root['artifact_id']==report['artifact_id']
    assert second_root['package_sha256']==report['package_sha256']
    assert report['record_count']==1 and report['manifest']['parent_input']==before
    assert report['manifest']['environmental_margin_m']==0
    assert not report['catalogue_entry']['enabled']  # Never auto-verify/enable an official source.
    data=acquire_file(prepared_source(report),area,HttpCache(tmp_path/'cache'))
    assert data.records[0]['source_well_id']=='000123'
    assert data.records[0]['geometry']['coordinates']==(500000.0,5900000.0)
    assert set(data.inspection['fields'])=={'COMPANY','ID'}
    assert data.inspection['regional_extract']['parent_input']==before
    assert not list((tmp_path/'extracts').glob('.preparing-*'))


def test_large_parent_is_not_copied_to_the_ingestion_cache(tmp_path,area):
    original=tmp_path/'original.gpkg'
    gpd.GeoDataFrame({'ID':['001'],'COMPANY':['Synthetic']},geometry=[Point(500000,5900000)],crs=3400).to_file(original,driver='GPKG',layer='surface')
    archive=tmp_path/'large.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED) as z:
        z.write(original,'original.gpkg');z.writestr('unrelated-padding.bin',b'x'*(1024*1024))
    report=prepare_extract(source(archive,file_layer='surface'),area,tmp_path/'extracts')
    assert archive.stat().st_size>1024*1024 and report['package_bytes']<65536
    data=acquire_file(prepared_source(report),area,HttpCache(tmp_path/'cache',max_bytes=65536))
    assert len(data.records)==1
    assert all(p.stat().st_size<65536 for p in (tmp_path/'cache').rglob('*') if p.is_file())


def test_mismatched_scope_mapping_and_corrupt_package_are_rejected(tmp_path,area):
    path=tmp_path/'original.geojson'
    gpd.GeoDataFrame({'ID':['001'],'COMPANY':['Synthetic']},geometry=[Point(500000,5900000)],crs=3400).to_file(path,driver='GeoJSON')
    report=prepare_extract(source(path),area,tmp_path/'extracts');item=prepared_source(report)
    wider=area.model_copy(update={'bbox_wgs84':(-116,52,-114,54)})
    with pytest.raises(ValueError,match='use the original publisher input'):
        prepare_extract(item,wider,tmp_path/'nested-extracts')
    assert not (tmp_path/'nested-extracts').exists()
    with pytest.raises(ValueError,match='different study area'):
        acquire_file(item,wider,HttpCache(tmp_path/'wide-cache'))
    item=Source.model_validate(item.model_dump()|{'field_mapping':{'source_well_id':'ID'}})
    with pytest.raises(ValueError,match='mapping differs'):
        acquire_file(item,area,HttpCache(tmp_path/'mapped-cache'))
    report_path=Path(report['package_path']).parent/'report.json'
    report_path.write_text(report_path.read_text().replace(report['package_sha256'],'0'*64))
    with pytest.raises(ValueError,match='immutable regional extract is corrupt'):
        prepare_extract(source(path),area,tmp_path/'extracts')


def test_limit_failure_is_not_a_truncated_extract_and_preserves_previous_package(tmp_path,area):
    path=tmp_path/'original.geojson'
    gpd.GeoDataFrame({'ID':['one','two'],'COMPANY':['Synthetic']*2},geometry=[Point(500000,5900000),Point(500010,5900000)],crs=3400).to_file(path,driver='GeoJSON')
    item=source(path)
    first=prepare_extract(item,area,tmp_path/'extracts')
    with pytest.raises(ValueError,match='no truncation'):
        prepare_extract(item,area,tmp_path/'extracts',max_records=1)
    with pytest.raises(ValueError,match='output byte cap'):
        prepare_extract(item,area,tmp_path/'extracts',max_output_bytes=1024)
    assert prepare_extract(item,area,tmp_path/'extracts')==first
    assert len(list((tmp_path/'extracts').iterdir()))==1


def test_environmental_extract_includes_margin_and_retains_original_geometry(tmp_path,area):
    right=study_geometry(area).bounds[2];y=study_geometry(area).centroid.y
    geometry=LineString([(right+100,y-10),(right+100,y+10)])
    path=tmp_path/'water.geojson'
    gpd.GeoDataFrame({'ID':['margin','far']},geometry=[geometry,LineString([(right+600,y-10),(right+600,y+10)])],crs=3400).to_file(path,driver='GeoJSON')
    item=source(path,key='water',category='water',field_mapping={'source_feature_id':'ID'})
    report=prepare_extract(item,area,tmp_path/'extracts')
    data=acquire_file(prepared_source(report),area,HttpCache(tmp_path/'cache'))
    assert report['manifest']['environmental_margin_m']==500
    assert [r['source_feature_id'] for r in data.records]==['margin']
    assert data.records[0]['geometry']['coordinates']==tuple(geometry.coords)


def test_ambiguous_layers_unknown_crs_and_unsafe_archive_fail_before_output(tmp_path,area):
    path=tmp_path/'original.gpkg'
    for layer in ['surface','bottom']:
        gpd.GeoDataFrame({'ID':['001'],'COMPANY':['Synthetic']},geometry=[Point(500000,5900000)],crs=3400).to_file(path,driver='GPKG',layer=layer)
    assert len(inspect_original(source(path))[2]['available_layers'])==2
    with pytest.raises(ValueError,match='multiple layers'):
        prepare_extract(source(path),area,tmp_path/'extracts')
    with pytest.raises(ValueError,match='CRS'):
        prepare_extract(source(path,file_layer='surface',native_crs='EPSG:4326'),area,tmp_path/'extracts')
    sidecar=Path(str(path)+'-wal');sidecar.write_bytes(b'active writer')
    with pytest.raises(ValueError,match='sidecars'):
        inspect_original(source(path,file_layer='surface'))
    sidecar.unlink()
    shapefile=tmp_path/'unpackaged.shp';shapefile.write_bytes(b'fixture')
    with pytest.raises(ValueError,match='ZIP multi-file'):
        inspect_original(source(shapefile))
    bad=tmp_path/'unsafe.zip'
    with zipfile.ZipFile(bad,'w') as z:z.writestr('../bad.gdb/data','bad')
    with pytest.raises(ValueError,match='unsafe'):
        inspect_original(source(bad))
    assert not (tmp_path/'extracts').exists()


def test_changing_original_and_tampered_embedded_data_fail(tmp_path,area,monkeypatch):
    from src.sources import extract
    path=tmp_path/'original.geojson'
    gpd.GeoDataFrame({'ID':['001'],'COMPANY':['Synthetic']},geometry=[Point(500000,5900000)],crs=3400).to_file(path,driver='GeoJSON')
    real=extract.parent_fingerprint;calls=[]
    def changed(p):
        value=real(p);calls.append(1)
        return value if len(calls)==1 else {**value,'sha256':'0'*64}
    monkeypatch.setattr(extract,'parent_fingerprint',changed)
    with pytest.raises(ValueError,match='changed during preparation'):
        prepare_extract(source(path),area,tmp_path/'extracts')
    assert not list((tmp_path/'extracts').iterdir())
    monkeypatch.setattr(extract,'parent_fingerprint',real)
    report=prepare_extract(source(path),area,tmp_path/'extracts')
    package=Path(report['package_path'])
    with zipfile.ZipFile(package) as z:
        manifest=z.read('extract_manifest.json')
    with zipfile.ZipFile(package,'w') as z:
        z.writestr('extract_manifest.json',manifest);z.writestr('extract.gpkg',b'corrupt')
    with pytest.raises(ValueError,match='data checksum mismatch'):
        acquire_file(prepared_source(report),area,HttpCache(tmp_path/'cache'))
