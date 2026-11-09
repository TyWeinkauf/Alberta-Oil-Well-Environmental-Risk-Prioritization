"""Interactive screening UI. Run with: streamlit run app.py"""
import json
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine
from streamlit_folium import st_folium

from src.config import ROOT, database_url, load_source_catalog
import yaml
from src.contracts.spatial import CATEGORIES
from src.exports.selection import FIELDS, csv_bytes, geojson_bytes, table_records
from src.orchestrator import run_demo
from src.db.workflow import WorkflowBusy
from src.ui.data import list_analyzed_runs, load_dashboard, pipeline_attempts
from src.ui.map import build_map
from src.ui.model import filtered_wells, map_selection
from src.sources.pipeline import live_requirements, run_live
from src.production.store import load_demo_production, production_requirements, refresh_production
from src.production.view import production_view
from src.production.ui import show_production_audit, show_well_production

st.set_page_config(page_title='Alberta well screening',page_icon='🌿',layout='wide')
MISSING = 'Not available from this source'


@st.cache_resource
def connection_pool(url):
    return create_engine(url,pool_pre_ping=True)


def clear_filters():
    for key,value in {'companies':[],'statuses':[],'categories':['water'],'threshold':500,'matches_only':False}.items():
        st.session_state[key] = value


def choose_well():
    st.session_state.selected_well = st.session_state.detail_choice


def main():
    st.title('Alberta well screening')
    st.caption('Educational proximity screening — not an environmental risk assessment or an operational recommendation.')
    st.caption('Use the demo for an offline check, or run verified real sources once the source catalogue is ready.')
    try:
        engine = connection_pool(database_url())
    except Exception:
        st.error('Configure DATABASE_URL for local PostgreSQL/PostGIS using README.md, then restart the app.')
        st.stop()
    st.session_state.setdefault('busy',False)
    st.session_state.setdefault('selected_well',None)
    st.session_state.setdefault('actions',[])
    st.sidebar.header('Workflow')
    demo_requested=st.sidebar.button('Use demo dataset',type='primary',disabled=st.session_state.busy)
    try:
        catalog=load_source_catalog()
        requirements=live_requirements(catalog)
    except Exception:
        catalog=None;requirements=['Source catalogue configuration is invalid; inspect config/source_catalog.yml.']
    live_requested=st.sidebar.button('Run full pipeline',disabled=st.session_state.busy or bool(requirements),
        help='Run all verified analytical sources for the configured pilot; source snapshots are cached.')
    if requirements:
        with st.sidebar.expander('Live source readiness'):
            for requirement in requirements:st.write(requirement)
    if demo_requested or live_requested:
        st.session_state.busy = True
        stages = []
        action='Use demo dataset' if demo_requested else 'Run full pipeline'
        with st.status('Preparing dataset',expanded=True) as status:
            def progress(message):
                stages.append(message)
                st.write(message)
            try:
                run_id = run_demo(engine,progress) if demo_requested else run_live(engine,catalog=catalog,progress=progress)['run_id']
                st.session_state.run_choice = run_id
                st.session_state.selected_well = None
                st.session_state.last_map_event = None
                status.update(label='Demo ready' if demo_requested else 'Live dataset ready',state='complete')
                outcome = 'Complete'
            except WorkflowBusy as exc:
                status.update(label='Another workflow is running',state='error')
                st.warning(str(exc))
                outcome = 'Busy'
            except Exception as exc:
                # Do not render raw database exceptions or connection credentials.
                status.update(label='Workflow action failed',state='error')
                st.error(f'Workflow could not complete ({type(exc).__name__}). Check PostgreSQL/PostGIS, source metadata/network access and README.md. Previously analyzed results remain selectable if valid.')
                outcome = 'Failed'
            finally:
                st.session_state.busy = False
            st.session_state.actions.append({'time_utc':datetime.now(timezone.utc).isoformat(),
                                            'action':action,'outcome':outcome,'stages':' → '.join(stages)})
    try:
        runs = list_analyzed_runs(engine)
    except Exception:
        st.warning('No analyzed dataset is available. Use the demo button to initialize a configured database; check README.md if the service is unavailable.')
        st.stop()
    if not runs:
        st.info('Choose “Use demo dataset” to prepare the offline demonstration.')
        st.stop()
    run_lookup = {r['run_id']:r for r in runs}
    if st.session_state.get('run_choice') not in run_lookup:
        st.session_state.run_choice = runs[0]['run_id']
    run_id = st.sidebar.selectbox('Study area / dataset',list(run_lookup),key='run_choice',
        format_func=lambda k:f'{run_lookup[k]["study_area"]["name"]} · {run_lookup[k]["started_at"][:10]} · {k[:8]}')
    if st.session_state.get('previous_run') != run_id:
        st.session_state.selected_well = None
        st.session_state.last_map_event = None
        st.session_state.previous_run = run_id
        clear_filters()
    try:
        dashboard = load_dashboard(engine,run_id)
    except Exception:
        st.error('This dataset cannot currently be read. Re-run analysis or choose another analyzed dataset.')
        st.stop()
    if dashboard['study_area'].get('mode')=='demo':
        st.info('Synthetic demonstration data. These are test fixtures, not real AER wells or government environmental layers.')
    else:
        st.info('Real-source dataset. Inspect provenance, coverage and quarantine records before interpreting proximity results.')
    # Production is outside the current scope; only an explicit enabled custom source exposes the retained workflow.
    production_source=next((s for s in catalog.sources if s.role=='production' and s.enabled),None) if catalog else None
    if production_source is not None:
        production_blockers=production_requirements(production_source)
        with st.sidebar.expander('Production'):
            window=yaml.safe_load((ROOT/'config/production_window.yml').read_text())
            production_start=st.text_input('Production start month',window['start'])
            production_end=st.text_input('Production end month',window['end'])
            demo_production=st.button('Load synthetic production demo',disabled=st.session_state.busy or dashboard['study_area']['mode']!='demo')
            real_production=st.button('Refresh production',disabled=st.session_state.busy or bool(production_blockers) or dashboard['study_area']['mode']!='live')
            if production_blockers:st.caption('Official production remains unverified; refresh is disabled. The demo uses project-authored observations only.')
        if demo_production or real_production:
            st.session_state.busy=True
            with st.status('Updating production',expanded=True) as production_status:
                try:
                    result=(load_demo_production(engine,run_id,start=production_start,end=production_end) if demo_production else
                            refresh_production(engine,run_id,start=production_start,end=production_end,source=production_source))
                    dashboard=load_dashboard(engine,run_id)
                    production_status.update(label='Production ready',state='complete')
                    st.session_state.actions.append({'time_utc':datetime.now(timezone.utc).isoformat(),'action':'Production update',
                        'outcome':'Complete','stages':f'Active batch {result["batch_id"]}; {result["source_mode"]}'})
                except WorkflowBusy as exc:
                    production_status.update(label='Another workflow is running',state='error')
                    st.warning(str(exc))
                    st.session_state.actions.append({'time_utc':datetime.now(timezone.utc).isoformat(),'action':'Production update',
                        'outcome':'Busy','stages':'Another workflow owns the database lock'})
                except Exception as exc:
                    production_status.update(label='Production update failed',state='error')
                    st.error(f'Production could not update ({type(exc).__name__}); the previous active batch remains available. Check source metadata, identifier evidence and network settings.')
                    st.session_state.actions.append({'time_utc':datetime.now(timezone.utc).isoformat(),'action':'Production update',
                        'outcome':'Failed','stages':type(exc).__name__})
                finally:st.session_state.busy=False
    st.sidebar.header('Filters')
    companies = sorted({r['licensee_name'] or MISSING for r in dashboard['wells']})
    statuses = sorted({r['status'] or MISSING for r in dashboard['wells']})
    st.sidebar.multiselect('Company (licensee)',companies,key='companies',help='An empty selection includes all companies. Licensee does not imply operator or producer.')
    st.sidebar.multiselect('Well status',statuses,key='statuses',help='An empty selection includes all statuses.')
    st.sidebar.multiselect('Environmental categories',sorted(CATEGORIES),key='categories')
    st.sidebar.selectbox('Distance threshold (m)',[50,100,250,500],key='threshold')
    st.sidebar.checkbox('Only wells within threshold',key='matches_only')
    st.sidebar.button('Clear filters',on_click=clear_filters)
    st.sidebar.caption('Unknown coverage is not evidence of no nearby environmental feature.')
    records = filtered_wells(dashboard,st.session_state.categories,st.session_state.threshold,
                             st.session_state.companies,st.session_state.statuses,st.session_state.matches_only)
    selection = {'run_id':run_id,'categories':sorted(st.session_state.categories),'threshold_m':st.session_state.threshold,
                 'companies':st.session_state.companies,'statuses':st.session_state.statuses,'matches_only':st.session_state.matches_only}
    metrics = st.columns(4)
    metrics[0].metric('Visible wells',len(records))
    metrics[1].metric('Within threshold',sum(r['matches_threshold'] is True for r in records))
    metrics[2].metric('Unknown threshold result',sum(r['matches_threshold'] is None for r in records))
    metrics[3].metric('Spatial quarantines',len(dashboard['quarantine']))
    st.caption(f'Run {run_id} · loaded {dashboard["started_at"]} · ingestion {dashboard["ingestion_status"]} · spatial results analyzed')
    map_tab,quality_tab,history_tab = st.tabs(['Map & results','Data quality','Run history'])
    with map_tab:
        st.caption('Categories: '+(', '.join(selection['categories']) or 'none')+
                   f' · threshold {selection["threshold_m"]} m · licensees: '+(', '.join(selection['companies']) or 'all')+
                   ' · statuses: '+(', '.join(selection['statuses']) or 'all')+
                   (' · showing known threshold matches only' if selection['matches_only'] else ' · showing all filtered wells'))
        options = st.columns(2)
        basemap = options[0].checkbox('Show OpenStreetMap basemap (online)',value=False)
        overlays = options[1].checkbox('Show environmental geometry',value=True)
        view = build_map(records,dashboard['features'],st.session_state.categories,basemap=basemap,overlays=overlays)
        event = st_folium(view,key=f'screening-map-{run_id}',height=430,use_container_width=True,
            returned_objects=['last_object_clicked_popup','last_object_clicked_count'])
        selected,event_key = map_selection(event,{r['well_pk'] for r in records},st.session_state.get('last_map_event'))
        st.session_state.last_map_event = event_key
        if selected is not None:
            st.session_state.selected_well = selected
        st.caption('Bands: red ≤50 m · orange >50–100 m · yellow >100–250 m · blue >250–500 m · gray >500 m or unknown (see table). Map positions use WGS84; distances use EPSG:3400 metres.')
        visible = {r['well_pk']:r for r in records}
        st.session_state.detail_choice = st.session_state.selected_well if st.session_state.selected_well in visible else None
        st.selectbox('Inspect a well',[None,*visible],key='detail_choice',on_change=choose_well,
                     format_func=lambda k:'Choose a well or click a marker' if k is None else visible[k]['source_well_id'])
        if st.session_state.selected_well is not None and st.session_state.selected_well not in visible:
            st.warning('Selected well is outside current filters. Clear the selection or change the filters.')
            if st.button('Clear selection'):
                st.session_state.selected_well = None
                st.rerun()
        elif st.session_state.selected_well in visible:
            well = visible[st.session_state.selected_well]
            st.subheader('Well details')
            st.text(well['source_well_id'])
            left,right = st.columns(2)
            with left:
                for label,field in [('Licensee','licensee_name'),('Verified operator','operator_name_if_verified'),
                                    ('UWI','uwi_if_available'),('LSD / legal location','lsd_text'),('Status','status')]:
                    st.text(f'{label}: {well[field] or MISSING}')
            with right:
                st.text(f'Latitude: {well["latitude"]:.7f}\nLongitude: {well["longitude"]:.7f}\nBand: {well["band"]}')
                st.text(f'Source: {well["source_key"]}\nSnapshot retrieved: {well["retrieved_at"]}\nSource CRS: {well["native_crs"]}')
            st.dataframe(pd.DataFrame([r for r in dashboard['proximity'] if r['well_pk']==well['well_pk']]),hide_index=True)
            if production_source is not None:
                show_well_production(production_view(engine,run_id,well['well_pk']))
        st.subheader('Filtered results')
        table = pd.DataFrame(table_records(records),columns=FIELDS)
        st.dataframe(table,hide_index=True)
        if not records:
            st.info('No wells match the current filters. Clear filters to show all wells.')
        st.subheader('Export current selection')
        downloads = st.columns(3)
        downloads[0].download_button('Download CSV',csv_bytes(records),'well_selection.csv','text/csv',on_click='ignore')
        downloads[1].download_button('Download GeoJSON',geojson_bytes(records,selection),'well_selection.geojson','application/geo+json',on_click='ignore')
        # streamlit-folium rewrites the displayed figure; export an independent
        # figure so its normalized map_div cannot duplicate the standalone map.
        export_map = build_map(records,dashboard['features'],st.session_state.categories,basemap=basemap,overlays=overlays)
        downloads[2].download_button('Download map HTML',export_map.get_root().render().encode(),'well_map.html','text/html',on_click='ignore')
        manifest = {'selection':selection,'count':len(records),'sources':dashboard['sources'],
                    'coverage':dashboard['coverage'],'study_area':dashboard['study_area'],
                    'disclaimer':'Educational proximity screening; not an operational risk assessment.',
                    'mode':dashboard['study_area']['mode']}
        st.download_button('Download selection manifest',json.dumps(manifest,indent=2).encode(),'selection_manifest.json','application/json',on_click='ignore')
    with quality_tab:
        st.subheader('Source provenance and coverage')
        st.dataframe(pd.DataFrame(dashboard['sources']),hide_index=True)
        st.dataframe(pd.DataFrame(dashboard['coverage']),hide_index=True)
        st.caption('Quarantined environmental features can make a category incomplete. Incomplete and unavailable results stay unknown.')
        st.subheader('Quarantined records')
        st.dataframe(pd.DataFrame(dashboard['quarantine']),hide_index=True)
        validation = {'run_id':run_id,'input_records':sum(r['record_count'] for r in dashboard['sources'] if r['source_role']=='analysis'),
                      'accepted_wells':len(dashboard['wells']),'accepted_features':len(dashboard['features']),
                      'rejected_records':len(dashboard['quarantine']),'quarantined':dashboard['quarantine'],
                      'coverage':dashboard['coverage']}
        st.download_button('Download validation records',json.dumps(validation,indent=2).encode(),'validation.json','application/json',on_click='ignore')
        if production_source is not None:
            show_production_audit(production_view(engine,run_id))
    with history_tab:
        st.subheader('Analyzed datasets')
        st.dataframe(pd.DataFrame([{'run_id':r['run_id'],'started_at':r['started_at'],'study_area':r['study_area']['name']} for r in runs]),hide_index=True)
        st.subheader('Workflow actions in this session')
        st.dataframe(pd.DataFrame(st.session_state.actions),hide_index=True)
        st.subheader('Live pipeline attempts')
        st.dataframe(pd.DataFrame(pipeline_attempts(engine)),hide_index=True)
        st.caption('Live attempt stages and error classes are retained without connection credentials.')


main()
