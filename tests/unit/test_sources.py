import json
import threading
import zipfile
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point

from src.config import Source, load_study_area
from src.contracts.spatial import validate_records
from src.sources.arcgis import acquire_arcgis
from src.sources.files import acquire_file, spatial_path
from src.sources.http import HttpCache
from src.spatial.extent import study_geometry


@contextmanager
def serve(route):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status,headers,body=route(urlsplit(self.path).path,parse_qs(urlsplit(self.path).query),self.headers)
            self.send_response(status)
            for key,value in headers.items():self.send_header(key,value)
            self.end_headers();self.wfile.write(body)
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield f'http://127.0.0.1:{server.server_port}'
    finally:server.shutdown();server.server_close();thread.join()


def test_http_cache_checksums_conditional_refresh_retry_and_size_cap(tmp_path):
    calls=[];failures={'left':1}
    def route(path,query,headers):
        calls.append((path,dict(headers)))
        if path=='/retry' and failures['left']:
            failures['left']-=1
            return 503,{},b'temporary failure'
        if headers.get('If-None-Match')=='"fixture"':return 304,{},b''
        return 200,{'Content-Length':'7','ETag':'"fixture"'},b'fixture'
    with serve(route) as base:
        cache=HttpCache(tmp_path/'cache',max_bytes=100)
        first=cache.get(base+'/retry')
        assert len(calls)==2
        assert cache.get(base+'/retry')==first and len(calls)==2
        assert cache.get(base+'/retry',refresh=True)==first and len(calls)==3
        with pytest.raises(ValueError,match='byte limit'):
            HttpCache(tmp_path/'small',max_bytes=2).get(base+'/large')
        budget=HttpCache(tmp_path/'budget',max_bytes=100,max_total_bytes=10)
        budget.get(base+'/one')
        with pytest.raises(ValueError,match='total transfer budget'):
            budget.get(base+'/two')
        first.path.write_bytes(b'corrupt')
        with pytest.raises(ValueError,match='checksum mismatch'):
            cache.get(base+'/retry')


def test_unencrypted_remote_and_embedded_credentials_are_rejected(tmp_path):
    cache=HttpCache(tmp_path)
    for url in ['http://example.com/data','https://user:password@example.com/data']:
        with pytest.raises(ValueError):cache.get(url)


def arcgis_route(*,missing=False):
    def route(path,query,headers):
        if not path.endswith('/query'):
            value={'supportedQueryFormats':'JSON, geoJSON','maxRecordCount':1,'objectIdField':'OID',
                   'fields':[{'name':'OID','type':'esriFieldTypeOID'},{'name':'LABEL','type':'esriFieldTypeString'}],
                   'extent':{'spatialReference':{'wkid':3400}},'editingInfo':{'lastEditDate':1000}}
        elif query.get('returnCountOnly')==['true']:value={'count':2}
        elif query.get('returnIdsOnly')==['true']:value={'objectIds':[2,1]}
        else:
            ids=[int(i) for i in query['objectIds'][0].split(',')]
            value={'type':'FeatureCollection','features':[
                {'type':'Feature','properties':{'OID':i,'LABEL':f'Synthetic-{i}'},
                 'geometry':{'type':'LineString','coordinates':[[-115,53.25],[-115,53.26]]}} for i in ids if not missing]}
        return 200,{'Content-Type':'application/json'},json.dumps(value).encode()
    return route


def test_arcgis_metadata_id_batches_and_bounded_request_are_complete(tmp_path):
    with serve(arcgis_route()) as base:
        source=Source(key='synthetic_water',kind='arcgis',url=base+'/MapServer',layer_id=0,
                      native_crs='EPSG:3400',category='water',field_mapping={'source_feature_id':'OID','name':'LABEL'})
        acquisition=acquire_arcgis(source,load_study_area(),HttpCache(tmp_path))
        assert [r['source_feature_id'] for r in acquisition.records]==['1','2']
        assert len(acquisition.responses)==5
        assert acquisition.records_crs=='EPSG:4326' and acquisition.native_crs=='EPSG:3400'
        assert acquisition.inspection['environmental_margin_m']==500


def test_arcgis_missing_page_record_cannot_be_treated_as_empty_coverage(tmp_path):
    with serve(arcgis_route(missing=True)) as base:
        source=Source(key='synthetic_water',kind='arcgis',url=base+'/MapServer',layer_id=0,
                      native_crs='EPSG:3400',category='water',field_mapping={'source_feature_id':'OID'})
        with pytest.raises(ValueError,match='missing, duplicate or unexpected'):
            acquire_arcgis(source,load_study_area(),HttpCache(tmp_path))


@pytest.mark.parametrize('driver,extension',[('GPKG','.gpkg'),('ESRI Shapefile','.shp'),('OpenFileGDB','.gdb')])
def test_spatial_file_formats_crs_and_subset_are_inspected(tmp_path,driver,extension):
    frame=gpd.GeoDataFrame({'IDENT':['in','far'],'COMPANY':['Synthetic A','Synthetic B']},
                          geometry=[Point(500000,5900000),Point(0,0)],crs=3400)
    folder=tmp_path/'source';folder.mkdir()
    dataset=folder/('fixture'+extension)
    frame.to_file(dataset,driver=driver,engine='pyogrio',layer='fixture' if extension!='.shp' else None)
    archive=tmp_path/'source.zip'
    with zipfile.ZipFile(archive,'w') as target:
        for path in folder.rglob('*'):
            if path.is_file():target.write(path,path.relative_to(folder))
    payload=archive.read_bytes()
    with serve(lambda *args:(200,{'Content-Type':'application/zip'},payload)) as base:
        source=Source(key='synthetic_wells',kind='file',url=base+'/download',native_crs='EPSG:3400',
                      field_mapping={'source_well_id':'IDENT','licensee_name':'COMPANY'})
        acquisition=acquire_file(source,load_study_area(),HttpCache(tmp_path/'cache'))
        assert acquisition.inspection['driver'] in ('GPKG','ESRI Shapefile','OpenFileGDB')
        assert [r['source_well_id'] for r in acquisition.records]==['in']


def test_zip_path_safety_and_ambiguous_dataset_rejection(tmp_path):
    bad=tmp_path/'bad.zip'
    with zipfile.ZipFile(bad,'w') as archive:archive.writestr('../escape.shp','not a dataset')
    with pytest.raises(ValueError,match='unsafe'):spatial_path(bad)
    with zipfile.ZipFile(bad,'w') as archive:
        archive.writestr('one.shp','fixture');archive.writestr('two.shp','fixture')
    with pytest.raises(ValueError,match='ambiguous'):spatial_path(bad)


def test_live_features_use_actual_500_m_buffer_instead_of_unbuffered_bbox():
    area=load_study_area().model_copy(update={'mode':'live','bbox_wgs84':(-115.001,53.269,-114.999,53.271)})
    region=study_geometry(area)
    right=region.bounds[2]
    y=region.centroid.y
    from shapely.geometry import mapping
    rows=[{'source_feature_id':'within-margin','category':'water','geometry':mapping(LineString([(right+100,y-20),(right+100,y+20)]))},
          {'source_feature_id':'outside-margin','category':'water','geometry':mapping(LineString([(right+600,y-20),(right+600,y+20)]))}]
    result=validate_records(rows,'features','EPSG:3400',area)
    assert len(result.accepted)==1 and result.accepted[0]['source_feature_id']=='within-margin'
    assert result.rejected[0]['reason_code']=='outside_study_area'
