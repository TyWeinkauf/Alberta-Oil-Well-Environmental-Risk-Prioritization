import json

import pytest
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
