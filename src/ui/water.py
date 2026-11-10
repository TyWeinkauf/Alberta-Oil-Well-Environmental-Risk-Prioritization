"""Explicit water-import controls and an independent, immutable inventory preview."""
import json
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from src.db.workflow import WorkflowBusy
from src.sources.hydrography import import_waterways, latest_water_import, water_features, water_requirements
from src.ui.map import build_map


@st.cache_data(ttl=60, max_entries=8)
def cached_water_features(_engine, database_identity, import_id):
    return water_features(_engine, import_id)


def show_waterways(engine, catalog):
    with st.sidebar.expander('Waterways'):
        seasonal = st.checkbox('Include seasonal waterways', key='water_seasonal',
                               help='Adds verified optional recurring waterbody and intermittent-stream layers.')
        refresh = st.checkbox('Recheck water source updates', key='water_refresh')
        missing = water_requirements(catalog, seasonal) if catalog else ['Configure a valid source catalogue.']
        requested = st.button('Import waterways', key='import_waterways',
                              disabled=st.session_state.busy or bool(missing),
                              help='Imports the configured real study area plus 500 m; does not download the entire province.')
        for reason in missing:
            st.caption(reason)
        st.caption('Water imports are independent of synthetic demo wells and complete screening runs.')
        preview = st.checkbox('Preview imported waterways', key='water_preview')
    if requested:
        st.session_state.busy = True
        stages, outcome = [], 'Failed'
        with st.status('Importing study-area waterways', expanded=True) as status:
            def progress(message):
                stages.append(message)
                st.text(message)
            try:
                result = import_waterways(engine, catalog=catalog, include_optional=seasonal,
                                          refresh=refresh, progress=progress)
                st.session_state.water_import_choice = result['import_id']
                status.update(label=f'Waterways ready: {result["feature_count"]} features', state='complete')
                outcome = 'Complete'
            except WorkflowBusy as exc:
                status.update(label='Another workflow is running', state='error')
                st.warning(str(exc))
                outcome = 'Busy'
            except Exception as exc:
                status.update(label='Water import failed', state='error')
                st.error(f'Waterways could not update ({type(exc).__name__}). Check the database, source metadata and network. The previous inventory remains available.')
            finally:
                st.session_state.busy = False
            st.session_state.actions.append({'time_utc': datetime.now(timezone.utc).isoformat(),
                'action': 'Import waterways', 'outcome': outcome, 'stages': ' → '.join(stages)})
    try:
        report = latest_water_import(engine, st.session_state.get('water_import_choice'))
    except Exception:
        # A fresh database may not have the screening schema yet. Explicit imports
        # apply migrations; ordinary rerenders remain read-only.
        st.sidebar.caption('Water inventory unavailable; configure the database and import waterways.')
        return
    if not report:
        st.sidebar.caption('No waterways have been imported into this database.')
        return
    area = report['study_area']
    st.sidebar.caption(f'Water inventory: {report["feature_count"]} features · {area["name"]} · {report["coverage_status"]}')
    if not preview:
        return
    st.subheader('Imported waterways')
    st.caption(f'{area["name"]} plus 500 m · {report["feature_count"]} features · inventory {report["import_id"][:8]}')
    if report['coverage_status'] != 'complete':
        st.warning('Some water features were quarantined. Water coverage is incomplete; inspect the manifest.')
    st.caption('Independent real-water inventory preview. These features are not combined with synthetic wells; well distances require a complete real-source screening run.')
    features = cached_water_features(engine, engine.url.render_as_string(hide_password=True), report['import_id'])
    basemap = st.checkbox('Show OpenStreetMap on water preview', key='water_basemap')
    view = build_map([], features, ['water'], basemap=basemap)
    west, south, east, north = area['bbox_wgs84']
    view.fit_bounds([[south, west], [north, east]], padding=(20, 20))
    st.iframe(view.get_root().render(), height=350, alt='Imported waterbody polygons and stream lines in the study area')
    st.dataframe(pd.DataFrame([{key: row[key] for key in ('source_key','source_feature_id','name','feature_type_code')}
                               for row in features]), hide_index=True, alt='Imported waterways and source classification codes')
    st.download_button('Download water inventory manifest', json.dumps(report, indent=2).encode(),
                       'water_inventory_manifest.json', 'application/json', key='water_manifest', on_click='ignore')
