"""Prepared FileGDB subsets use the real PostGIS path; fixtures are entirely synthetic."""
from datetime import datetime, timezone

import geopandas as gpd
import pytest
from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon
from sqlalchemy import text

from src.config import ROOT, Source, SourceCatalog, load_study_area
from src.sources.extract import prepare_extract
from src.sources.http import HttpCache
from src.sources.pipeline import run_live
from src.ui.data import load_dashboard

pytestmark=pytest.mark.integration


def test_regional_filegdb_packages_load_atomically_keep_margin_and_reject_wider_area(test_engine,tmp_path):
    area=load_study_area(ROOT/'config/study_area.live.yml')
    edge_x,edge_y=Transformer.from_crs(4326,3400,always_xy=True).transform(area.bbox_wgs84[2]-.00001,53.25)
    original=tmp_path/'synthetic.gdb'
    gpd.GeoDataFrame({'ID':['000123','000124','far'],'COMPANY':['Synthetic']*3},
        geometry=[Point(500000,5900000),Point(edge_x,edge_y),Point(0,0)],crs=3400).to_file(original,driver='OpenFileGDB',layer='surface')
    water=[LineString([(500050,5899990),(500050,5900010)]),
           LineString([(edge_x+100,edge_y-10),(edge_x+100,edge_y+10)])]
    gpd.GeoDataFrame({'ID':['near','margin']},geometry=water,crs=3400).to_file(original,driver='OpenFileGDB',layer='water')
    for layer,offset in [('parks',0),('habitat',250)]:
        x=500000+offset
        polygon=Polygon([(x-10,5899990),(x+10,5899990),(x+10,5900010),(x-10,5900010)])
        gpd.GeoDataFrame({'ID':[layer]},geometry=[polygon],crs=3400).to_file(original,driver='OpenFileGDB',layer=layer)
    shared=dict(kind='file',local_path=original,native_crs='EPSG:3400',enabled=True,verified=True,
                publisher='Synthetic test publisher',metadata_url='https://example.invalid/synthetic',
                downloaded_at=datetime(2026,11,8,tzinfo=timezone.utc),license_note='Project-authored synthetic only',
                coverage_note='Closed synthetic world covers region and margin')
    sources=[Source(key='aer_wells',file_layer='surface',field_mapping={'source_well_id':'ID','licensee_name':'COMPANY'},**shared)]
    for key,category,layer in [('alberta_water','water','water'),('alberta_protected_areas','protected_area','parks'),
                               ('federal_critical_habitat','critical_habitat','habitat')]:
        sources.append(Source(key=key,category=category,file_layer=layer,field_mapping={'source_feature_id':'ID'},**shared))
    prepared=[]
    for source in sources:
        report=prepare_extract(source,area,tmp_path/'extracts')
        prepared.append(Source.model_validate(report['catalogue_entry']|{'local_path':report['package_path']}))
    catalog=SourceCatalog(sources=prepared)
    def run(study):
        return run_live(test_engine,catalog=catalog,area=study,cache=HttpCache(tmp_path/'cache'),
                        raw_root=tmp_path/'raw',output_root=tmp_path/'runs')
    first=run(area)
    assert run(area)==first
    assert first['counts']=={'wells':2,'features':4,'quarantined':0,'proximity_rows':10}
    dashboard=load_dashboard(test_engine,first['run_id'])
    keys={w['source_well_id']:w['well_pk'] for w in dashboard['wells']}
    distances={p['well_pk']:p['distance_m'] for p in dashboard['proximity'] if p['category']=='water'}
    assert distances[keys['000123']]==pytest.approx(50,abs=.01)
    assert distances[keys['000124']]==pytest.approx(100,abs=.01)
    assert all(s['inspection']['regional_extract']['parent_input']['kind']=='filegdb_directory' for s in first['sources'])
    west,south,east,north=area.bbox_wgs84
    wider=area.model_copy(update={'bbox_wgs84':(west-.01,south,east+.01,north)})
    with pytest.raises(ValueError,match='different study area'):
        run(wider)
    with test_engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM screening.pipeline_runs')).scalar_one()==1
        assert conn.execute(text('SELECT count(*) FROM screening.well_proximity')).scalar_one()==10
        assert conn.execute(text("SELECT count(*) FROM screening.pipeline_attempts WHERE status='failed'")).scalar_one()==1
