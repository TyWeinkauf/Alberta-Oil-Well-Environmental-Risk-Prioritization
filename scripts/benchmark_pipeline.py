"""Bounded synthetic performance check in an initially empty disposable _test database."""
import argparse
import csv
import os
import platform
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from _bootstrap import run_cli
import geopandas as gpd
from shapely.geometry import LineString, Polygon
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from src.artifacts import write_json
from src.config import ROOT, Source, SourceCatalog, load_study_area
from src.db.workflow import workflow_lock
from src.exports.selection import csv_bytes
from src.sources.http import HttpCache
from src.sources.pipeline import run_live
from src.ui.data import load_dashboard
from src.ui.model import filtered_wells


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wells',type=int,default=1000)
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/verification/benchmark.json')
    args=parser.parse_args()
    if not 1<=args.wells<=10000:
        raise ValueError('Choose between 1 and 10,000 synthetic wells')
    url=os.getenv('TEST_DATABASE_URL')
    if not url or not (make_url(url).database or '').endswith('_test'):
        raise ValueError('Set TEST_DATABASE_URL to a separate empty database ending in _test')
    engine=create_engine(url,pool_pre_ping=True)
    try:
        with workflow_lock(engine):
            with engine.connect() as conn:
                if conn.execute(text("SELECT to_regnamespace('screening')")).scalar_one() is not None:
                    raise ValueError('Benchmark refuses an existing screening schema')
            # Only this initially absent schema is ours; retain unrelated database contents.
            try:
                with tempfile.TemporaryDirectory(prefix='alberta-benchmark-') as directory:
                    root=Path(directory)
                    wells=root/'wells.csv'
                    with wells.open('w',newline='') as handle:
                        writer=csv.writer(handle);writer.writerow(['ID','COMPANY','X','Y'])
                        for i in range(args.wells):
                            writer.writerow([f'SYNTHETIC-{i:06}',f'Synthetic company {i%4}',500000+(i%100)*5,5900000+(i//100)*5])
                    common=dict(kind='file',enabled=True,verified=True,publisher='Project-authored synthetic benchmark',
                                downloaded_at=datetime(2026,11,8,tzinfo=timezone.utc),
                                metadata_url='https://example.invalid/synthetic-benchmark',license_note='Synthetic benchmark only',
                                coverage_note='Closed synthetic world covers the pilot and its 500 m margin.')
                    sources=[Source(key='aer_wells',local_path=wells,native_crs='EPSG:3400',csv_x_field='X',csv_y_field='Y',
                                    field_mapping={'source_well_id':'ID','licensee_name':'COMPANY'},**common)]
                    for key,category in [('alberta_water','water'),('alberta_protected_areas','protected_area'),('federal_critical_habitat','critical_habitat')]:
                        geometries=[]
                        for i in range(10):
                            x=500000+i*50
                            geometries.append(LineString([(x,5899900),(x,5900600)]) if category=='water' else
                                Polygon([(x,5899900),(x+20,5899900),(x+20,5900600),(x,5900600)]))
                        path=root/(key+'.geojson')
                        gpd.GeoDataFrame({'ID':[str(i) for i in range(10)]},geometry=geometries,crs=3400).to_crs(4326).to_file(path,driver='GeoJSON')
                        sources.append(Source(key=key,category=category,local_path=path,native_crs='EPSG:4326',
                                              field_mapping={'source_feature_id':'ID'},**common))
                    catalog=SourceCatalog(sources=sources)
                    area=load_study_area(ROOT/'config/study_area.live.yml')
                    def run():
                        return run_live(engine,catalog=catalog,area=area,cache=HttpCache(root/'cache'),
                                        max_records=10000,raw_root=root/'raw',output_root=root/'runs')
                    start=perf_counter();first=run();first_seconds=perf_counter()-start
                    start=perf_counter();second=run();repeat_seconds=perf_counter()-start
                    if first['run_id']!=second['run_id'] or first['counts']!=second['counts']:
                        raise ValueError('Benchmark rerun identity/counts changed')
                    with engine.connect() as conn:
                        versions=conn.execute(text('SELECT version(),postgis_version()')).one()
                        if conn.execute(text('SELECT count(*) FROM screening.pipeline_runs')).scalar_one()!=1:
                            raise ValueError('Benchmark created duplicate runs')
                    start=perf_counter()
                    dashboard=load_dashboard(engine,first['run_id'])
                    selection=filtered_wells(dashboard,['water'],500,[],[],False)
                    exported=csv_bytes(selection)
                    view_seconds=perf_counter()-start
                    report={'mode':'synthetic_benchmark','generator_version':1,'wells_requested':args.wells,
                            'counts':first['counts'],'first_run_seconds':round(first_seconds,4),
                            'repeat_run_seconds':round(repeat_seconds,4),'dashboard_filter_export_seconds':round(view_seconds,4),
                            'exported_rows':len(selection),'csv_bytes':len(exported),'repeat_identity_matches':True,
                            'python':platform.python_version(),'postgresql':versions[0],'postgis':versions[1],
                            'source_identities':first['source_identities'],
                            'limitations':'Local synthetic inputs, 30 features, two runs; not province-wide performance or official data. Temporary inputs/schema are removed.'}
                    write_json(args.output,report)
                    print(f'Synthetic benchmark: {args.wells} wells; first {first_seconds:.3f}s; repeat {repeat_seconds:.3f}s; dashboard/export {view_seconds:.3f}s')
                    print(f'Evidence: {args.output}')
            finally:
                with engine.begin() as conn:
                    conn.execute(text('DROP SCHEMA IF EXISTS screening CASCADE'))
    finally:
        engine.dispose()


if __name__=='__main__':
    run_cli(main,error_hint='Use an empty disposable _test database and see docs/release_verification.md.')
