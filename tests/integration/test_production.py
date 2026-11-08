import json

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from streamlit.testing.v1 import AppTest

from src.config import ROOT, Source
from src.db.demo import seed_demo
from src.db.migrations import migrate
from src.production.store import import_csv, load_demo_production, refresh_production
from src.production.view import production_view
from src.spatial.engine import analyze_run

pytestmark=pytest.mark.integration


@pytest.fixture
def production_run(test_engine,tmp_path):
    migrate(test_engine)
    result=seed_demo(test_engine,raw_root=tmp_path/'geo-raw',output_root=tmp_path/'geo-runs')
    analyze_run(test_engine,result['run_id'])
    return result['run_id']


def load(engine,run,tmp_path):
    return load_demo_production(engine,run,raw_root=tmp_path/'production-raw',output_root=tmp_path/'production-runs')


def test_production_import_is_idempotent_and_facility_volumes_never_enter_well_chart(test_engine,production_run,tmp_path):
    first=load(test_engine,production_run,tmp_path);second=load(test_engine,production_run,tmp_path)
    assert first==second
    assert first['validation']=={'input_records':9,'accepted':6,'quarantined':2,'excluded_outside_window':1,
        'reason_counts':{'invalid_period':1,'missing_fields':1},
        'link_status_counts':{'verified':3,'facility':1,'unmatched':1,'unknown':1}}
    with test_engine.connect() as conn:
        wells=conn.execute(text('SELECT well_pk FROM screening.wells ORDER BY source_well_id')).scalars().all()
        assert conn.execute(text('SELECT count(*) FROM screening.production_batches')).scalar_one()==1
        assert conn.execute(text('SELECT count(*) FROM screening.production_monthly')).scalar_one()==6
    a=production_view(test_engine,production_run,wells[0]);b=production_view(test_engine,production_run,wells[1])
    assert len(a['verified'])==3 and not b['verified']
    assert all(row['unit']=='m3' and row['product']=='OIL' for row in a['verified'])
    assert 'SYNTH-FACILITY' not in {row['source_record_id'] for row in a['verified']}
    assert any(row['link_status']=='facility' and row['volume']=='900.00' for row in a['audit'])
    assert a['batch']['source_mode']=='synthetic' and len(a['quarantine'])==2
    json.dumps(a,allow_nan=False)


def test_ambiguous_target_identifiers_are_audited_and_not_charted(test_engine,production_run,tmp_path):
    with test_engine.begin() as conn:
        conn.execute(text("UPDATE screening.wells SET uwi_if_available='EXACT-UWI'"))
    source=Source(key='synthetic-uwi',kind='file',role='production',reporting_level='well',
                  well_identifier_field='uwi_if_available',identifier_namespace='synthetic-uwi',join_evidence='Test exact UWI',
                  field_mapping={'source_record_id':'ID','period':'MONTH','product':'PRODUCT','activity':'ACTIVITY',
                                 'volume':'VOLUME','unit':'UNIT','well_identifier_nullable':'WELL'})
    path=tmp_path/'ambiguous.csv';path.write_text('ID,MONTH,PRODUCT,ACTIVITY,VOLUME,UNIT,WELL\nA,2026-09,OIL,PRODUCTION,100,m3,EXACT-UWI\n')
    report=import_csv(test_engine,production_run,path,source,start='2026-09',end='2026-09',synthetic=True,
                      raw_root=tmp_path/'raw',output_root=tmp_path/'runs')
    assert report['validation']['link_status_counts']=={'ambiguous':1}
    with test_engine.connect() as conn:
        key=conn.execute(text('SELECT min(well_pk) FROM screening.wells')).scalar_one()
        assert conn.execute(text("SELECT count(*) FROM screening.production_well_links WHERE confidence_status='ambiguous'")).scalar_one()==2
    assert production_view(test_engine,production_run,key)['verified']==[]


def test_synthetic_production_cannot_attach_to_a_live_run(test_engine,production_run,tmp_path):
    with test_engine.begin() as conn:
        conn.execute(text("UPDATE screening.pipeline_runs SET study_area=jsonb_set(study_area,'{mode}','\"live\"')"))
    with pytest.raises(ValueError,match='never be attached'):
        load(test_engine,production_run,tmp_path)
    with test_engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM screening.production_batches')).scalar_one()==0


def test_failed_refresh_retains_previous_active_batch(test_engine,production_run,tmp_path):
    first=load(test_engine,production_run,tmp_path)
    with test_engine.begin() as conn:
        conn.execute(text("UPDATE screening.wells SET uwi_if_available='CHANGED-JOIN-EVIDENCE' WHERE source_well_id='DEMO-WELL-001'"))
        conn.exec_driver_sql('''CREATE FUNCTION screening.block_production() RETURNS trigger LANGUAGE plpgsql AS
            $$ BEGIN RAISE EXCEPTION 'synthetic production failure'; END; $$;
            CREATE TRIGGER block_production BEFORE INSERT ON screening.production_monthly
            FOR EACH ROW EXECUTE FUNCTION screening.block_production();''')
    with pytest.raises(DBAPIError,match='synthetic production failure'):
        load(test_engine,production_run,tmp_path)
    assert production_view(test_engine,production_run)['batch']['batch_id']==first['batch_id']
    with test_engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM screening.production_batches')).scalar_one()==1
        assert conn.execute(text('SELECT count(*) FROM screening.production_monthly')).scalar_one()==6


def test_unverified_official_production_fails_without_download(test_engine,production_run):
    with pytest.raises(ValueError,match='preflight blocked'):
        refresh_production(test_engine,production_run,start='2026-08',end='2026-10')


def test_well_production_read_cannot_cross_analysis_run_scope(test_engine,production_run,tmp_path):
    load(test_engine,production_run,tmp_path)
    with pytest.raises(ValueError,match='does not belong'):
        production_view(test_engine,production_run,999999)


def test_streamlit_demo_production_chart_and_unavailable_other_well(test_engine,production_run,tmp_path,monkeypatch):
    load(test_engine,production_run,tmp_path)
    monkeypatch.setenv('DATABASE_URL',test_engine.url.render_as_string(hide_password=False))
    app=AppTest.from_file(str(ROOT/'app.py')).run(timeout=30)
    with test_engine.connect() as conn:
        wells=conn.execute(text('SELECT well_pk FROM screening.wells ORDER BY source_well_id')).scalars().all()
    app.selectbox(key='detail_choice').select(wells[0]).run()
    assert not app.exception
    assert any(s.label=='Production series' for s in app.selectbox)
    assert any('Latest reported month: 2026-09' in c.value for c in app.caption)
    assert len(app.get('vega_lite_chart'))==1
    app.selectbox(key='detail_choice').select(wells[1]).run()
    assert not app.exception
    assert any('production not available/verified' in i.value for i in app.info)
    assert len(app.get('vega_lite_chart'))==0


def test_remote_failure_is_persisted_without_exposing_credentials(test_engine,production_run):
    import requests
    with test_engine.begin() as conn:
        conn.execute(text("UPDATE screening.pipeline_runs SET study_area=jsonb_set(study_area,'{mode}','\"live\"')"))
    source=Source(key='synthetic-remote',kind='file',role='production',enabled=True,verified=True,
        url='https://example.invalid/synthetic.csv',license_note='Synthetic protocol fixture only',
        field_mapping={'source_record_id':'ID','period':'MONTH','product':'PRODUCT','activity':'ACTIVITY','volume':'VOLUME','unit':'UNIT'})
    class FailedCache:
        def get(self,*args,**kwargs):raise requests.ConnectionError('simulated source transport failure')
    with pytest.raises(requests.ConnectionError):
        refresh_production(test_engine,production_run,start='2026-08',end='2026-10',source=source,cache=FailedCache())
    with test_engine.connect() as conn:
        row=conn.execute(text('SELECT status,stage,error_code,error_summary FROM screening.pipeline_attempts')).one()
        assert row.status=='failed' and row.stage=='production:acquire' and row.error_code=='ConnectionError'
        assert 'simulated source transport failure' not in row.error_summary
