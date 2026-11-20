"""Explicit Streamlit actions for provincial hydrography and retained ST37 wells."""
from datetime import datetime, timezone
from uuid import UUID

import pandas as pd
import streamlit as st

from src.config import ROOT
from src.db.st37 import import_st37_workbook
from src.db.waterbodies import (
    compare_st37_waterbodies, find_waterbody_comparison, waterbody_comparison_summary,
    waterbody_result, waterbody_workflow_snapshots,
)
from src.db.workflow import WorkflowBusy
from src.sources.waterbodies import PROVINCE_STREAM_SCOPE, import_province_streams, import_province_waterbodies
from src.spatial.classification import THRESHOLDS

ST37_WORKBOOK = ROOT / 'aida-final-project-tyler-weinkauf/courses/AIDA-1145/data/ST37_SH.xlsx'
ST37_RAW_ROOT = ROOT / 'data/raw/st37'


def run_action(label, action, completion):
    """Report explicit database actions through the existing session history."""
    st.session_state.busy = True
    result, outcome, stages = None, 'Failed', []
    try:
        with st.status(f'{label}…', expanded=True) as status:
            def progress(message):
                stages.append(message)
                st.text(message)

            try:
                result = action(progress)
                status.update(label=completion(result), state='complete')
                outcome = 'Complete'
            except WorkflowBusy as exc:
                status.update(label='Another workflow is running', state='error')
                st.warning(str(exc))
                outcome = 'Busy'
            except ValueError as exc:
                status.update(label=f'{label} failed', state='error')
                st.error(str(exc))
            except Exception as exc:
                status.update(label=f'{label} failed', state='error')
                st.error(f'{label} could not complete ({type(exc).__name__}). '
                         'Check the database connection and source availability.')
    finally:
        st.session_state.busy = False
        st.session_state.actions.append({'time_utc': datetime.now(timezone.utc).isoformat(),
                                         'action': label, 'outcome': outcome, 'stages': ' → '.join(stages)})
    return result if outcome == 'Complete' else None


def snapshot_select(label, key, rows, describe):
    by_id = {row['import_id']: row for row in rows}
    if not by_id:
        st.caption(f'{label} becomes available after import.')
        return None
    if st.session_state.get(key) not in by_id:
        st.session_state[key] = rows[0]['import_id']
    choice = st.selectbox(label, list(by_id), key=key, format_func=lambda item: describe(by_id[item]))
    return by_id[choice]


def well_choice(row):
    return (f'{row["imported_at"].astimezone(timezone.utc):%Y-%m-%d %H:%M UTC} · {row["accepted_count"]:,} wells · '
            f'{row["coordinate_crs"] or "datum pending"} · {str(row["import_id"])[:8]}')


def water_choice(row):
    unit = 'stream lines' if row['scope'] == PROVINCE_STREAM_SCOPE else 'waterbody polygons'
    return (f'{row["imported_at"].astimezone(timezone.utc):%Y-%m-%d %H:%M UTC} · {row["feature_count"]:,} {unit} · '
            f'{row["coverage_status"]} coverage · {str(row["import_id"])[:8]}')


def show_waterbody_workflow(engine):
    st.subheader('Alberta waterbodies, streams and ST37')
    water_controls, stream_controls, well_controls = st.columns(3)
    with water_controls:
        water_requested = st.button('Import Alberta waterbodies', key='import_province_waterbodies',
                                    disabled=st.session_state.busy, type='primary')
        st.caption('Loads the published layer-72 polygons into PostGIS in batches.')
    with stream_controls:
        streams_requested = st.button('Import Alberta streams', key='import_province_streams',
                                      disabled=st.session_state.busy, type='primary')
        st.caption('Loads the published layer-107 lines into PostGIS in batches.')
    with well_controls:
        workbook_exists = ST37_WORKBOOK.is_file()
        with st.expander('Workbook coordinate evidence'):
            st.caption('Leave both fields blank to stage the reported well coordinates. Enter the CRS and its evidence to enable distances.')
            crs = st.text_input('Workbook coordinate CRS', key='st37_coordinate_crs').strip()
            evidence = st.text_area('Publisher datum evidence', key='st37_crs_evidence').strip()
        well_requested = st.button('Import ST37 wells', key='import_st37_workbook', type='primary',
                                   disabled=st.session_state.busy or not workbook_exists or bool(crs) != bool(evidence))
        if workbook_exists:
            st.caption(f'Workbook {ST37_WORKBOOK.name} from the course data folder.')
        else:
            st.info('Place ST37_SH.xlsx in the AIDA 1145 data folder to enable the import.')
        if bool(crs) != bool(evidence):
            st.caption('Enter both coordinate fields or leave both blank.')

    if water_requested:
        result = run_action(
            'Import Alberta waterbodies', lambda progress: import_province_waterbodies(engine, progress=progress),
            lambda row: f'Alberta waterbodies ready · {row["feature_count"]:,} polygons',
        )
        if result:
            st.session_state.province_water_snapshot = UUID(result['import_id'])
    if streams_requested:
        result = run_action(
            'Import Alberta streams', lambda progress: import_province_streams(engine, progress=progress),
            lambda row: f'Alberta streams ready · {row["feature_count"]:,} lines',
        )
        if result:
            st.session_state.province_water_snapshot = UUID(result['import_id'])
    if well_requested:
        result = run_action(
            'Import ST37 wells',
            lambda progress: import_st37_workbook(engine, ST37_WORKBOOK, ST37_RAW_ROOT,
                                                  coordinate_crs=crs or None, crs_evidence=evidence or None,
                                                  progress=progress),
            lambda row: f'ST37 inventory ready · {row["accepted"]:,} accepted wells',
        )
        if result:
            st.session_state.province_well_snapshot = UUID(result['import_id'])

    try:
        wells, waters = waterbody_workflow_snapshots(engine)
    except Exception:
        st.warning('PostGIS inventory snapshots could not be read.')
        return
    water_picker, well_picker = st.columns(2)
    with water_picker:
        water = snapshot_select('Alberta hydrography snapshot', 'province_water_snapshot', waters, water_choice)
        if water:
            st.caption(f'{water["quarantined_count"]:,} records quarantined in this snapshot.')
            if water['scope'] == PROVINCE_STREAM_SCOPE:
                st.caption('Comparison uses perennial stream, canal, oxbow and ditch lines.')
    with well_picker:
        well = snapshot_select('ST37 well snapshot', 'province_well_snapshot', wells, well_choice)
    eligible = (water and water['feature_count'] and well and well['accepted_count']
                and well['coordinate_crs'] and well['crs_evidence'])
    streams = water is not None and water['scope'] == PROVINCE_STREAM_SCOPE
    comparison_kind = 'stream' if streams else 'waterbody'
    action = f'Run {comparison_kind} comparison'
    requested = st.button(action, key='compare_waterbodies',
                          disabled=st.session_state.busy or not eligible)
    if not eligible:
        st.caption('The comparison needs an imported hydrography snapshot and ST37 wells with a documented coordinate CRS.')
        return

    def compare(progress):
        progress('Calculating distances for the selected PostGIS inventories')
        return compare_st37_waterbodies(engine, well['import_id'], water['import_id'])

    if requested:
        run_action(action, compare, lambda _: f'{comparison_kind.capitalize()} comparison ready')
    try:
        comparison_id = find_waterbody_comparison(engine, well['import_id'], water['import_id'])
        if comparison_id is None:
            st.info('Run the comparison for the selected inventories to see their results.')
            return
        show_stored_comparison(engine, comparison_id)
    except Exception:
        st.warning('The stored waterbody comparison could not be read from PostGIS.')


@st.cache_data(max_entries=8)
def cached_province_summary(_engine, database_identity, comparison_id):
    return waterbody_comparison_summary(_engine, comparison_id)


def show_stored_comparison(engine, comparison_id):
    summary = cached_province_summary(engine, engine.url.render_as_string(hide_password=True), comparison_id)
    feature = 'layer-107 stream line' if summary['scope'] == PROVINCE_STREAM_SCOPE else 'layer-72 polygon'
    st.caption(f'{summary["well_count"]:,} ST37 wells · comparison {comparison_id}')
    if summary['coverage_status'] == 'incomplete':
        st.warning('Counts show matches to accepted features. Other wells may have unknown results because some records were quarantined.')
    st.dataframe(pd.DataFrame([
        {'Threshold (m)': metres, 'Observed matches': summary[f'within_{metres}']} for metres in THRESHOLDS
    ]), hide_index=True, alt=f'Observed ST37 matches to {feature} features by threshold')
    st.caption(f'{summary["unknown_within_500"]:,} wells with unknown 500 m results · '
               f'{summary["no_feature_within_500"]:,} with no {feature} within 500 m')
    licence = st.text_input('ST37 licence number', key='province_water_licence').strip()
    if licence:
        result = waterbody_result(engine, comparison_id, licence)
        if result:
            st.dataframe(pd.DataFrame([result]), hide_index=True, alt='Stored ST37 waterbody proximity for the selected licence')
        else:
            st.info('No matching licence in this comparison. Include any leading zeros.')
