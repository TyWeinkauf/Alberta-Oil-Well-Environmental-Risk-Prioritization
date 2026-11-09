"""End-to-end synthetic user-downloaded files; never official compatibility evidence."""
import json
import zipfile
from datetime import datetime, timezone

import geopandas as gpd
import pytest
import yaml
from shapely.geometry import LineString, Polygon
from sqlalchemy import text
from streamlit.testing.v1 import AppTest

from src.config import ROOT, Source, SourceCatalog, load_source_catalog, load_study_area
from src.production.store import refresh_production
from src.production.view import production_view
from src.sources.http import HttpCache
from src.sources.pipeline import run_live
from src.ui.data import load_dashboard

pytestmark=pytest.mark.integration


@pytest.fixture(params=['csv','zip'])
def file_catalog(tmp_path,request):
    shared=dict(enabled=True,verified=True,publisher='Project-authored synthetic test publisher',
                downloaded_at=datetime(2026,11,8,tzinfo=timezone.utc),metadata_url='https://example.invalid/synthetic',
                license_note='Project-authored synthetic test files, not official data',
                coverage_note='Synthetic complete pilot and 500 m margin')
    wells=tmp_path/'wells.csv'
    wells.write_text('ID,COMPANY,X,Y\n000123,Synthetic Company,500000,5900000\n')
    sources=[Source(key='aer_wells',kind='file',local_path=wells,native_crs='EPSG:3400',
        csv_x_field='X',csv_y_field='Y',field_mapping={'source_well_id':'ID','licensee_name':'COMPANY'},**shared)]
    polygon=Polygon([(499900,5899900),(500100,5899900),(500100,5900100),(499900,5900100)])
    for key,category in [('alberta_water','water'),('alberta_protected_areas','protected_area'),
                         ('federal_critical_habitat','critical_habitat')]:
        path=tmp_path/(key+'.geojson')
        geometry=LineString([(500050,5899900),(500050,5900100)]) if category=='water' else polygon
        gpd.GeoDataFrame({'ID':['001'],'NAME':['Synthetic geometry']},geometry=[geometry],crs=3400).to_crs(4326).to_file(path,driver='GeoJSON')
        sources.append(Source(key=key,kind='file',local_path=path,native_crs='EPSG:4326',category=category,
            field_mapping={'source_feature_id':'ID','name':'NAME'},**shared))
    production=tmp_path/'production.csv'
    production.write_text('ID,MONTH,PRODUCT,ACTIVITY,VOLUME,UNIT,LEVEL,WELL\n'
                          'one,2026-09,OIL,PRODUCTION,12.50,m3,W,000123\n'
                          'facility,2026-09,OIL,PRODUCTION,900,m3,F,000123\n')
    if request.param=='zip':
        zipped=tmp_path/'production.zip'
        with zipfile.ZipFile(zipped,'w') as archive:
            archive.write(production,'production.csv')
        production=zipped
    sources.append(Source(key='petrinex_production',kind='file',role='production',local_path=production,
        reporting_level='mixed',attribution_values={'W':'well','F':'facility'},
        well_identifier_field='source_well_id',identifier_namespace='synthetic-local-id',
        join_evidence='Both project-authored fixtures use exactly the same synthetic identifier.',
        field_mapping={'source_record_id':'ID','period':'MONTH','product':'PRODUCT','activity':'ACTIVITY',
                       'volume':'VOLUME','unit':'UNIT','attribution_level':'LEVEL','well_identifier_nullable':'WELL'},**shared))
    path=tmp_path/'catalog.yml'
    path.write_text(yaml.safe_dump(SourceCatalog(sources=sources).model_dump(mode='json')))
    return path


def run(engine,catalog,tmp_path):
    return run_live(engine,catalog=catalog,area=load_study_area(ROOT/'config/study_area.live.yml'),
                    cache=HttpCache(tmp_path/'cache'),raw_root=tmp_path/'raw',output_root=tmp_path/'runs')


def refresh(engine,run_id,source,tmp_path):
    return refresh_production(engine,run_id,source=source,start='2026-09',end='2026-09',
                              cache=HttpCache(tmp_path/'cache'),raw_root=tmp_path/'raw',output_root=tmp_path/'runs')


def test_local_files_load_spatial_and_verified_production_without_network(test_engine,file_catalog,tmp_path,monkeypatch):
    import requests
    monkeypatch.setattr(requests.Session,'get',lambda *a,**kw:pytest.fail('No network for local files'))
    catalog=load_source_catalog(file_catalog)
    first=run(test_engine,catalog,tmp_path);second=run(test_engine,catalog,tmp_path)
    assert first==second
    assert first['counts']=={'wells':1,'features':3,'quarantined':0,'proximity_rows':5}
    assert all(s['raw_responses'][0]['acquisition_mode']=='local_file' for s in first['sources'])
    dashboard=load_dashboard(test_engine,first['run_id'])
    assert next(p for p in dashboard['proximity'] if p['category']=='water')['distance_m']==pytest.approx(50,abs=0.01)
    source=next(s for s in catalog.sources if s.role=='production')
    a=refresh(test_engine,first['run_id'],source,tmp_path)
    assert refresh(test_engine,first['run_id'],source,tmp_path)==a
    view=production_view(test_engine,first['run_id'],dashboard['wells'][0]['well_pk'])
    assert len(view['verified'])==1 and view['verified'][0]['volume']=='12.50'
    assert a['validation']['link_status_counts']=={'verified':1,'facility':1}
    assert a['acquisition']['downloaded_at']=='2026-11-08T00:00:00+00:00'
    monkeypatch.setenv('DATABASE_URL',test_engine.url.render_as_string(hide_password=False))
    monkeypatch.setenv('SOURCE_CATALOG_PATH',str(file_catalog))
    app=AppTest.from_file(str(ROOT/'app.py')).run(timeout=30)
    assert not app.exception
    assert not next(b for b in app.button if b.label=='Run full pipeline').disabled
    assert not next(b for b in app.button if b.label=='Refresh production').disabled
    app.selectbox(key='detail_choice').select(dashboard['wells'][0]['well_pk']).run()
    assert not app.exception
    next(t for t in app.text_input if t.label=='Production start month').input('2026-09')
    next(t for t in app.text_input if t.label=='Production end month').input('2026-09')
    app.run()
    next(b for b in app.button if b.label=='Refresh production').click().run()
    assert not app.exception
    assert len(app.get('vega_lite_chart'))==1
    with test_engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM screening.pipeline_runs')).scalar_one()==1
        assert conn.execute(text('SELECT count(*) FROM screening.production_batches')).scalar_one()==1


def test_missing_or_invalid_local_refresh_retains_prior_results(test_engine,file_catalog,tmp_path):
    catalog=load_source_catalog(file_catalog);first=run(test_engine,catalog,tmp_path)
    source=next(s for s in catalog.sources if s.role=='production')
    batch=refresh(test_engine,first['run_id'],source,tmp_path)
    source.local_path.write_text('wrong,headers\nnot,a production record\n')
    with pytest.raises(ValueError,match='headers'):
        refresh(test_engine,first['run_id'],source,tmp_path)
    assert production_view(test_engine,first['run_id'])['batch']['batch_id']==batch['batch_id']
    next(s for s in catalog.sources if s.key=='alberta_water').local_path.unlink()
    with pytest.raises(ValueError,match='regular file'):
        run(test_engine,catalog,tmp_path)
    assert load_dashboard(test_engine,first['run_id'])['ingestion_status']=='succeeded'
    with test_engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM screening.pipeline_runs')).scalar_one()==1
        assert conn.execute(text("SELECT count(*) FROM screening.pipeline_attempts WHERE status='failed'")).scalar_one()==2
    manifest=json.loads((tmp_path/'runs'/first['run_id']/'production'/batch['batch_id']/'manifest.json').read_text())
    assert manifest['acquisition']['acquisition_mode']=='local_file'
