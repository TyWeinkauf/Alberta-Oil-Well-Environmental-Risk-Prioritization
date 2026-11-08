import json
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import geopandas as gpd
import pytest
from shapely.geometry import Point
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from src.config import ROOT, Source, SourceCatalog, load_source_catalog, load_study_area
from src.sources.http import HttpCache
from src.sources.pipeline import live_requirements, run_live
from src.ui.data import load_dashboard

pytestmark=pytest.mark.integration


@pytest.fixture
def local_sources(tmp_path):
    """Only simulated official-protocol inputs; no claim of real AER field names."""
    dataset=tmp_path/'wells.gpkg'
    gpd.GeoDataFrame({'IDENT':['SYNTHETIC-LIVE-001'],'COMPANY':['Synthetic protocol company']},
                     geometry=[Point(500000,5900000)],crs=3400).to_file(dataset,driver='GPKG',engine='pyogrio')
    archive=tmp_path/'wells.zip'
    with zipfile.ZipFile(archive,'w') as z:z.write(dataset,'wells.gpkg')
    binary=archive.read_bytes();state={'missing_page':False,'revision':1,'requests':0}
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            state['requests']+=1
            parsed=urlsplit(self.path);query=parse_qs(parsed.query)
            if parsed.path=='/wells.zip':
                body=binary;content='application/zip'
            else:
                if not parsed.path.endswith('/query'):
                    value={'supportedQueryFormats':'JSON,geoJSON','maxRecordCount':1,'objectIdField':'OID',
                           'fields':[{'name':'OID','type':'esriFieldTypeOID'},{'name':'LABEL','type':'esriFieldTypeString'}],
                           'extent':{'spatialReference':{'wkid':3400}}}
                elif query.get('returnCountOnly')==['true']:value={'count':1}
                elif query.get('returnIdsOnly')==['true']:value={'objectIds':[1]}
                else:
                    layer=int(parsed.path.split('/')[-2])
                    geometry=({'type':'LineString','coordinates':[[-115.001,53.26],[-115.001,53.28]]} if layer==0 else
                              {'type':'Polygon','coordinates':[[[-115.002,53.269],[-114.998,53.269],[-114.998,53.272],[-115.002,53.272],[-115.002,53.269]]]})
                    value={'type':'FeatureCollection','features':[] if state['missing_page'] and layer==0 else
                           [{'type':'Feature','properties':{'OID':1,'LABEL':f'Synthetic revision {state["revision"]}'},'geometry':geometry}]}
                body=json.dumps(value).encode();content='application/json'
            self.send_response(200);self.send_header('Content-Type',content);self.end_headers();self.wfile.write(body)
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    shared={'enabled':True,'verified':True,'native_crs':'EPSG:3400',
            'license_note':'Synthetic local protocol test data, not an official product licence',
            'coverage_note':'Synthetic test source covers the pilot plus its 500 m margin.'}
    sources=[Source(key='aer_wells',kind='file',url=base+'/wells.zip',
                    field_mapping={'source_well_id':'IDENT','licensee_name':'COMPANY'},**shared)]
    for layer,(key,category) in enumerate([('alberta_water','water'),('alberta_protected_areas','protected_area'),
                                          ('federal_critical_habitat','critical_habitat')]):
        sources.append(Source(key=key,kind='arcgis',url=base+'/MapServer',layer_id=layer,category=category,
                              field_mapping={'source_feature_id':'OID','name':'LABEL'},**shared))
    try:yield SourceCatalog(sources=sources),state
    finally:server.shutdown();server.server_close();thread.join()


def run(engine,catalog,tmp_path,**kwargs):
    return run_live(engine,catalog=catalog,cache=HttpCache(tmp_path/'cache'),
                    area=load_study_area(ROOT/'config/study_area.live.yml'),
                    raw_root=tmp_path/'raw',output_root=tmp_path/'runs',**kwargs)


def test_live_protocol_load_is_atomic_idempotent_and_auditable(test_engine,local_sources,tmp_path):
    catalog,state=local_sources
    first=run(test_engine,catalog,tmp_path)
    count=state['requests']
    second=run(test_engine,catalog,tmp_path)
    assert first['run_id']==second['run_id'] and state['requests']==count
    assert first['counts']=={'wells':1,'features':3,'quarantined':0,'proximity_rows':5}
    dashboard=load_dashboard(test_engine,first['run_id'])
    assert dashboard['study_area']['mode']=='live' and len(dashboard['sources'])==4
    raw_retrieval={source['source_key']:max(r['retrieved_at'] for r in source['raw_responses']) for source in first['sources']}
    assert all(source['retrieved_at']==raw_retrieval[source['source_key']] for source in dashboard['sources'])
    assert next(r for r in dashboard['proximity'] if r['category']=='protected_area')['distance_m']==0
    assert first['coverage']['critical_habitat']['status']=='complete'
    assert first['coverage']['wetland']['status']=='unavailable'
    report=json.loads((tmp_path/'runs'/first['run_id']/'manifest.json').read_text())
    assert len(report['sources'])==4 and all(s['raw_responses'] for s in report['sources'])
    with test_engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM screening.pipeline_runs')).scalar_one()==1
        assert conn.execute(text("SELECT count(*) FROM screening.pipeline_attempts WHERE status='succeeded'")).scalar_one()==2


def test_incomplete_source_fails_without_replacing_prior_analyzed_run(test_engine,local_sources,tmp_path):
    catalog,state=local_sources
    first=run(test_engine,catalog,tmp_path)
    state['missing_page']=True
    with pytest.raises(ValueError,match='missing, duplicate or unexpected'):
        run(test_engine,catalog,tmp_path,refresh=True)
    with test_engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM screening.pipeline_runs')).scalar_one()==1
        assert conn.execute(text('SELECT count(*) FROM screening.well_proximity')).scalar_one()==5
        failure=conn.execute(text("SELECT stage,error_code FROM screening.pipeline_attempts WHERE status='failed'")).one()
        assert failure.stage=='acquire:alberta_water' and failure.error_code=='ValueError'
    assert load_dashboard(test_engine,first['run_id'])['ingestion_status']=='succeeded'


def test_spatial_load_failure_rolls_back_all_new_run_rows(test_engine,local_sources,tmp_path):
    catalog,state=local_sources
    first=run(test_engine,catalog,tmp_path)
    state['revision']=2
    with test_engine.begin() as conn:
        conn.exec_driver_sql('''CREATE FUNCTION screening.block_live() RETURNS trigger LANGUAGE plpgsql AS
            $$ BEGIN RAISE EXCEPTION 'synthetic live failure'; END; $$;
            CREATE TRIGGER block_live BEFORE INSERT ON screening.well_proximity
            FOR EACH ROW EXECUTE FUNCTION screening.block_live();''')
    with pytest.raises(DBAPIError,match='synthetic live failure'):
        run(test_engine,catalog,tmp_path,refresh=True)
    with test_engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM screening.pipeline_runs')).scalar_one()==1
        assert conn.execute(text('SELECT count(*) FROM screening.source_snapshots')).scalar_one()==4
        assert conn.execute(text('SELECT count(*) FROM screening.wells')).scalar_one()==1
        assert conn.execute(text("SELECT count(*) FROM screening.pipeline_attempts WHERE status='failed'")).scalar_one()==1
    assert load_dashboard(test_engine,first['run_id'])['run_id']==first['run_id']


def test_unverified_catalogue_blocks_before_creating_run_or_attempt(test_engine):
    assert live_requirements(load_source_catalog())
    with pytest.raises(ValueError,match='preflight is blocked'):
        run_live(test_engine)
    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT to_regnamespace('screening')")).scalar_one() is None
