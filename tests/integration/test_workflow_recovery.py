"""Real database sessions and a killed child process verify coordination/recovery."""
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from streamlit.testing.v1 import AppTest

from src.config import ROOT
from src.db.demo import seed_demo
from src.db.migrations import migrate
from src.db.workflow import WorkflowBusy, workflow_lock
from src.orchestrator import run_demo
from src.production.store import load_demo_production
from src.production.view import production_view
from src.spatial.engine import analyze_run
from src.ui.data import load_dashboard

pytestmark=pytest.mark.integration


def prepare(engine,tmp_path):
    migrate(engine)
    report=seed_demo(engine,raw_root=tmp_path/'raw',output_root=tmp_path/'runs')
    analyze_run(engine,report['run_id'])
    return report['run_id']


def test_concurrent_writer_is_rejected_while_reads_and_busy_ui_work(test_engine,tmp_path,monkeypatch):
    run=prepare(test_engine,tmp_path)
    ready=threading.Event();release=threading.Event()
    def owner():
        with workflow_lock(test_engine):
            ready.set()
            assert release.wait(15)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(owner)
        try:
            assert ready.wait(5)
            for action in [lambda:migrate(test_engine),lambda:run_demo(test_engine),
                           lambda:analyze_run(test_engine,run),lambda:load_demo_production(test_engine,run)]:
                with pytest.raises(WorkflowBusy,match='Another import'):
                    action()
            assert len(load_dashboard(test_engine,run)['wells'])==2
            monkeypatch.setenv('DATABASE_URL',test_engine.url.render_as_string(hide_password=False))
            app=AppTest.from_file(str(ROOT/'app.py')).run(timeout=10)
            next(b for b in app.button if b.label=='Use demo dataset').click().run(timeout=10)
            assert not app.exception
            assert any('Another import' in warning.value for warning in app.warning)
        finally:
            release.set()
        future.result(timeout=5)
    assert run_demo(test_engine)==run


def test_nested_workflows_and_exception_release_session_lock(test_engine):
    with pytest.raises(RuntimeError,match='forced'):
        with workflow_lock(test_engine):
            migrate(test_engine)  # Reuses the outer guard rather than a second lock session.
            with workflow_lock(test_engine):
                raise RuntimeError('forced')
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(migrate,test_engine).result(timeout=5)==[]


def test_guard_commit_error_does_not_return_a_locked_session_to_the_pool(test_engine,monkeypatch):
    original=Connection.commit
    fail_next=[True]
    def fail_once(conn):
        if fail_next[0]:
            fail_next[0]=False
            raise RuntimeError('Simulated guard commit failure')
        return original(conn)
    monkeypatch.setattr(Connection,'commit',fail_once)
    with pytest.raises(RuntimeError,match='guard commit failure'):
        with workflow_lock(test_engine):
            pytest.fail('Guard setup should have failed')
    # A distinct pool proves that the lock was released rather than reacquired recursively.
    peer=create_engine(test_engine.url)
    try:
        assert len(migrate(peer))==5
    finally:
        peer.dispose()


def test_killed_process_releases_lock_and_recovers_attempt_without_losing_active_data(test_engine,tmp_path):
    run=prepare(test_engine,tmp_path)
    kwargs={'raw_root':tmp_path/'production','output_root':tmp_path/'runs'}
    first=load_demo_production(test_engine,run,**kwargs)
    code='''
import os,sys
from uuid import uuid4
from sqlalchemy import create_engine,text
from src.db.workflow import LOCK_NAME
engine=create_engine(os.environ['TEST_DATABASE_URL'])
with engine.connect() as conn:
    assert conn.execute(text('SELECT pg_try_advisory_lock(hashtext(:name))'),{'name':LOCK_NAME}).scalar_one()
    conn.execute(text("INSERT INTO screening.pipeline_attempts(attempt_id,status,stage,study_area) VALUES (:id,'running','acquire:synthetic-interruption','{}'::jsonb)"),{'id':uuid4()})
    conn.commit()
    print('locked',flush=True)
    sys.stdin.buffer.read(1)
'''
    child=subprocess.Popen([sys.executable,'-c',code],cwd=ROOT,env=os.environ.copy(),
                           stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
    ready=threading.Event();output=[]
    def read_ready():
        output.append(child.stdout.readline().strip());ready.set()
    reader=threading.Thread(target=read_ready,daemon=True);reader.start()
    try:
        assert ready.wait(5), 'Child failed to acquire its test lock'
        assert output==['locked']
        with pytest.raises(WorkflowBusy):
            load_demo_production(test_engine,run,**kwargs)
        assert production_view(test_engine,run)['batch']['batch_id']==first['batch_id']
        child.kill();child.wait(timeout=5)
        # Client process exit and server socket-close detection are asynchronous,
        # particularly on Windows. Require recovery within a bounded interval.
        deadline=time.monotonic()+5
        while True:
            try:
                second=load_demo_production(test_engine,run,**kwargs)
                break
            except WorkflowBusy:
                if time.monotonic()>=deadline:
                    raise
                threading.Event().wait(0.01)
        assert first==second
        with test_engine.connect() as conn:
            attempt=conn.execute(text('SELECT status,error_code,finished_at FROM screening.pipeline_attempts')).one()
            assert attempt.status=='failed' and attempt.error_code=='InterruptedWorkflow' and attempt.finished_at
            assert conn.execute(text('SELECT count(*) FROM screening.production_batches')).scalar_one()==1
            assert conn.execute(text('SELECT count(*) FROM screening.well_proximity')).scalar_one()==10
    finally:
        if child.poll() is None:
            child.kill();child.wait(timeout=5)
        reader.join(timeout=5)
        child.stdin.close();child.stdout.close()


def test_manifest_export_failure_keeps_previous_active_production(test_engine,tmp_path,monkeypatch):
    from src.production import store
    run=prepare(test_engine,tmp_path)
    kwargs={'raw_root':tmp_path/'production','output_root':tmp_path/'runs'}
    first=load_demo_production(test_engine,run,**kwargs)
    original=store.write_json
    def fail(*args,**kwargs):
        raise OSError('Simulated report export failure')
    monkeypatch.setattr(store,'write_json',fail)
    with pytest.raises(OSError,match='export failure'):
        load_demo_production(test_engine,run,start='2026-09',end='2026-10',**kwargs)
    assert production_view(test_engine,run)['batch']['batch_id']==first['batch_id']
    monkeypatch.setattr(store,'write_json',original)
    recovered=load_demo_production(test_engine,run,start='2026-09',end='2026-10',**kwargs)
    assert production_view(test_engine,run)['batch']['batch_id']==recovered['batch_id']
