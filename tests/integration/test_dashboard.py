import json

import pytest
from sqlalchemy import text
from streamlit.testing.v1 import AppTest

from src.config import ROOT
from src.db.demo import seed_demo
from src.db.migrations import migrate
from src.spatial.engine import analyze_run
from src.ui.data import list_analyzed_runs, load_dashboard
from src.ui.model import filtered_wells

pytestmark=pytest.mark.integration


def test_dashboard_snapshot_agrees_with_spatial_rows_and_sources(test_engine,tmp_path):
    migrate(test_engine)
    report=seed_demo(test_engine,raw_root=tmp_path/'raw',output_root=tmp_path/'runs')
    assert list_analyzed_runs(test_engine)==[]
    analyze_run(test_engine,report['run_id'])
    dashboard=load_dashboard(test_engine,report['run_id'])
    assert list_analyzed_runs(test_engine)[0]['run_id']==report['run_id']
    assert len(dashboard['wells'])==2 and len(dashboard['proximity'])==10
    assert len(dashboard['quarantine'])==6
    assert dashboard['sources'][0]['checksum']==report['source']['checksum_sha256']
    assert filtered_wells(dashboard,['water'])[1]['distance_m']==150
    json.dumps(dashboard,allow_nan=False)


def test_streamlit_workflow_filter_selection_and_rerender_do_not_reload(test_engine,tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_URL',test_engine.url.render_as_string(hide_password=False))
    # Run real workflow steps, changing only generated artifact locations for tests.
    import src.orchestrator
    original=src.orchestrator.seed_demo
    monkeypatch.setattr(src.orchestrator,'seed_demo',lambda engine:original(engine,raw_root=tmp_path/'raw',output_root=tmp_path/'runs'))
    app=AppTest.from_file(str(ROOT/'app.py')).run(timeout=30)
    assert not app.exception
    app.button[0].click().run(timeout=30)
    assert not app.exception
    assert app.metric[0].value=='2'
    assert app.session_state.actions[-1]['outcome']=='Complete'
    # Select by the widget's actual stable DB key, not its displayed source label.
    dashboard=load_dashboard(test_engine,list_analyzed_runs(test_engine)[0]['run_id'])
    key=dashboard['wells'][0]['well_pk']
    app.selectbox(key='detail_choice').select(key).run()
    assert not app.exception
    assert app.session_state.selected_well==key
    assert not any(b.label in ('Refresh production','Load synthetic production demo') for b in app.button)
    assert not any(h.value=='Monthly production' for h in app.subheader)
    app.selectbox(key='threshold').select(50).run()
    assert app.metric[1].value=='1' and app.session_state.selected_well==key
    app.multiselect(key='companies').set_value(['Synthetic Company B']).run()
    assert app.metric[0].value=='1'
    assert any('outside current filters' in warning.value for warning in app.warning)
    assert app.session_state.selected_well==key
    assert len(app.session_state.actions)==1
    app.checkbox(key='matches_only').check().run()
    assert not app.exception and app.metric[0].value=='0'
    with test_engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM screening.pipeline_runs')).scalar_one()==1
        assert conn.execute(text('SELECT count(*) FROM screening.well_proximity')).scalar_one()==10
