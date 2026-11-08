"""Interactive screening UI. Run with: streamlit run app.py"""
import json
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine
from streamlit_folium import st_folium

from src.config import database_url
from src.contracts.spatial import CATEGORIES
from src.exports.selection import FIELDS, csv_bytes, geojson_bytes, table_records
from src.orchestrator import run_demo
from src.ui.data import list_analyzed_runs, load_dashboard
from src.ui.map import build_map
from src.ui.model import filtered_wells, map_selection

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
    st.info('Synthetic demonstration data. The completed project will use AER and government environmental sources; live downloads are not connected yet.')
    try:
        engine = connection_pool(database_url())
    except Exception:
        st.error('Configure DATABASE_URL for local PostgreSQL/PostGIS using README.md, then restart the app.')
        st.stop()
    st.session_state.setdefault('busy',False)
    st.session_state.setdefault('selected_well',None)
    st.session_state.setdefault('actions',[])
    st.sidebar.header('Workflow')
    if st.sidebar.button('Use demo dataset',type='primary',disabled=st.session_state.busy):
        st.session_state.busy = True
        stages = []
        with st.status('Preparing synthetic demonstration',expanded=True) as status:
            def progress(message):
                stages.append(message)
                st.write(message)
            try:
                run_id = run_demo(engine,progress)
                st.session_state.run_choice = run_id
                st.session_state.selected_well = None
                st.session_state.last_map_event = None
                status.update(label='Demo ready',state='complete')
                outcome = 'Complete'
            except Exception as exc:
                # Do not render raw database exceptions or connection credentials.
                status.update(label='Demo action failed',state='error')
                st.error(f'Demo could not complete ({type(exc).__name__}). Check PostgreSQL/PostGIS, DATABASE_URL and README.md. Previously analyzed results remain selectable if valid.')
                outcome = 'Failed'
            finally:
                st.session_state.busy = False
            st.session_state.actions.append({'time_utc':datetime.now(timezone.utc).isoformat(),
                                            'action':'Use demo dataset','outcome':outcome,'stages':' → '.join(stages)})
    st.sidebar.button('Run full pipeline',disabled=True,help='Live source adapters and verified endpoints are not connected yet.')
    st.sidebar.button('Refresh production',disabled=True,help='Production ingestion and verified well joins are a later milestone.')
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
    metrics[3].metric('Quarantined inputs',len(dashboard['quarantine']))
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
            st.info('Well-level production not available/verified. No facility volumes have been allocated to this well.')
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
                    'disclaimer':'Educational proximity screening; synthetic data; not an operational risk assessment.'}
        st.download_button('Download selection manifest',json.dumps(manifest,indent=2).encode(),'selection_manifest.json','application/json',on_click='ignore')
    with quality_tab:
        st.subheader('Source provenance and coverage')
        st.dataframe(pd.DataFrame(dashboard['sources']),hide_index=True)
        st.dataframe(pd.DataFrame(dashboard['coverage']),hide_index=True)
        st.caption('Quarantined environmental features can make a category incomplete. Incomplete and unavailable results stay unknown.')
        st.subheader('Quarantined records')
        st.dataframe(pd.DataFrame(dashboard['quarantine']),hide_index=True)
        validation = {'run_id':run_id,'input_records':sum(r['record_count'] for r in dashboard['sources']),
                      'accepted_wells':len(dashboard['wells']),'accepted_features':len(dashboard['features']),
                      'rejected_records':len(dashboard['quarantine']),'quarantined':dashboard['quarantine'],
                      'coverage':dashboard['coverage']}
        st.download_button('Download validation records',json.dumps(validation,indent=2).encode(),'validation.json','application/json',on_click='ignore')
    with history_tab:
        st.subheader('Analyzed datasets')
        st.dataframe(pd.DataFrame([{'run_id':r['run_id'],'started_at':r['started_at'],'study_area':r['study_area']['name']} for r in runs]),hide_index=True)
        st.subheader('Workflow actions in this session')
        st.dataframe(pd.DataFrame(st.session_state.actions),hide_index=True)
        st.caption('Persistent failed-run audit and real-data refresh history will be added with the live pipeline.')


main()
