"""Explicit Streamlit actions for provincial hydrography and retained ST37 wells."""
import json
from datetime import datetime, timezone
from secrets import randbits
from uuid import UUID

import pandas as pd
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from src.config import ROOT
from src.db.st37 import ST37_INVENTORY_PAGE_SIZE, import_st37_workbook, st37_import_snapshots, st37_inventory_page
from src.db.waterbodies import (
    WELL_MAP_BATCH_SIZE, compare_st37_waterbodies, find_waterbody_comparison, st37_water_comparisons,
    waterbody_comparison_summary, waterbody_map_batch, waterbody_result, waterbody_workflow_snapshots,
)
from src.db.workflow import WorkflowBusy
from src.sources.st37 import FIELDS as ST37_FIELDS
from src.sources.waterbodies import PROVINCE_STREAM_SCOPE, import_province_streams, import_province_waterbodies
from src.spatial.classification import THRESHOLDS
from src.ui.map import build_waterbody_batch_map

ST37_WORKBOOK = ROOT / 'aida-final-project-tyler-weinkauf/courses/AIDA-1145/data/ST37_SH.xlsx'
ST37_RAW_ROOT = ROOT / 'data/raw/st37'
ST37_ALBERTA_BOUNDARY_QA = ROOT / 'docs/evidence/st37_alberta_boundary_2026-11-23.json'


def audited_outside_rows(snapshot_id: UUID) -> tuple[int, ...]:
    """Apply the boundary audit only to the projected snapshot it checked."""
    try:
        audit = json.loads(ST37_ALBERTA_BOUNDARY_QA.read_bytes())
    except (OSError, ValueError):
        return ()
    if audit['st37_snapshot'] != str(snapshot_id):
        return ()
    return tuple(audit['outside_source_rows'])


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


def show_st37_import(engine, snapshot_key):
    workbook_exists = ST37_WORKBOOK.is_file()
    with st.expander('Workbook coordinate evidence'):
        st.caption('Leave both coordinate fields blank to stage the reported well coordinates. Enter the CRS and its evidence to enable distances.')
        crs = st.text_input('Workbook coordinate CRS', key='st37_coordinate_crs').strip()
        evidence = st.text_area('Publisher datum evidence', key='st37_crs_evidence').strip()
        release_date = st.date_input('Publisher release date (optional)', value=None, key='st37_release_date')
    requested = st.button('Import ST37 wells', key='import_st37_workbook', type='primary',
                          disabled=st.session_state.busy or not workbook_exists or bool(crs) != bool(evidence))
    if workbook_exists:
        st.caption(f'Workbook {ST37_WORKBOOK.name} from the course data folder.')
    else:
        st.info('Place ST37_SH.xlsx in the AIDA 1145 data folder to enable the import.')
    if bool(crs) != bool(evidence):
        st.caption('Enter both coordinate fields or leave both blank.')
    if requested:
        result = run_action(
            'Import ST37 wells',
            lambda progress: import_st37_workbook(engine, ST37_WORKBOOK, ST37_RAW_ROOT,
                                                  coordinate_crs=crs or None, crs_evidence=evidence or None,
                                                  release_date=release_date.isoformat() if release_date else None,
                                                  progress=progress),
            lambda row: f'ST37 inventory ready · {row["accepted"]:,} accepted wells',
        )
        if result:
            st.session_state[snapshot_key] = UUID(result['import_id'])


def show_st37_inventory(engine):
    st.subheader('AER ST37 surface-hole inventory')
    with st.sidebar:
        show_st37_import(engine, 'st37_inventory_snapshot')
    try:
        with engine.connect() as conn:
            snapshots = st37_import_snapshots(conn)
    except SQLAlchemyError:
        st.error('The ST37 inventory could not be read. Check the PostgreSQL connection.')
        return
    snapshot = snapshot_select('ST37 well snapshot', 'st37_inventory_snapshot', snapshots, well_choice)
    if snapshot is None:
        return

    records = snapshot['record_count']
    st.caption(f'{snapshot["worksheet"] or "ST37 worksheet"} · {records:,} workbook rows · {snapshot["accepted_count"]:,} accepted · '
               f'{snapshot["quarantined_count"]:,} quarantined · '
               f'release {snapshot["release_date"] or "unknown"} · '
               f'{snapshot["coordinate_crs"] or "coordinate datum pending"}')
    licence = st.text_input('Well licence number', key='st37_inventory_licence',
                            help='Enter the complete licence, including any leading zeros.').strip()
    try:
        comparisons = st37_water_comparisons(engine, snapshot['import_id']) if snapshot['coordinate_crs'] else []
    except SQLAlchemyError:
        comparisons = []
        st.warning('The stored water comparisons could not be read.')
    if comparisons:
        view = st.radio('Inventory view', ['Water proximity map', 'Workbook records'], horizontal=True,
                        key='st37_inventory_view')
        if view == 'Water proximity map':
            water = snapshot_select('Imported water layer', 'st37_inventory_water', comparisons, water_choice)
            try:
                show_stored_comparison(engine, water['comparison_id'], licence=licence, basemap_default=True)
            except (SQLAlchemyError, ValueError):
                st.warning('The selected water comparison could not be read from PostGIS.')
            return
    elif snapshot['coordinate_crs']:
        st.caption('Run a comparison for this snapshot under PostGIS workflows to enable the water proximity map.')
    else:
        st.caption('The water proximity map requires a documented workbook coordinate CRS.')
    offset = 0
    if not licence:
        last_page = (records + ST37_INVENTORY_PAGE_SIZE - 1) // ST37_INVENTORY_PAGE_SIZE
        page = st.number_input('Page', min_value=1, max_value=last_page, step=1,
                               key=f'st37_inventory_page_{snapshot["import_id"]}')
        offset = (page - 1) * ST37_INVENTORY_PAGE_SIZE
    try:
        rows = st37_inventory_page(engine, snapshot['import_id'], offset=offset, licence=licence)
    except SQLAlchemyError:
        st.error('The selected ST37 rows could not be read from PostgreSQL.')
        return
    if not rows:
        st.info('No rows match this selection. Enter the full licence number, including any leading zeros.')
        return
    if licence:
        st.caption(f'Showing up to {ST37_INVENTORY_PAGE_SIZE:,} exact licence matches.')
    else:
        st.caption(f'Rows {offset + 1:,}–{offset + len(rows):,} of {records:,} in workbook order.')
    outside = audited_outside_rows(snapshot['import_id'])
    table = [{
        'Workbook row': row['source_row'],
        **{field: row['raw_payload'][field] for field in ST37_FIELDS},
        'Validation errors': ', '.join(row['validation_errors']),
        'Quality warnings': ', '.join(row['quality_warnings']),
        **({'Boundary review': 'Reported position outside Alberta' if row['source_row'] in outside else ''}
           if outside else {}),
    } for row in rows]
    st.dataframe(pd.DataFrame(table), hide_index=True, alt='Original values from the selected AER ST37 workbook rows',
                 column_config={'Well_Licence_Number': 'Well licence', 'Licence_Status': 'Licence status',
                                'Licence_Surface_Location_Label': 'Legal location', 'SH_Actual_Latitude': 'Reported latitude',
                                'SH_Actual_Longitude': 'Reported longitude'})


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
        show_st37_import(engine, 'province_well_snapshot')

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


@st.cache_data(max_entries=4, show_spinner=False)
def cached_comparison_map(_engine, database_identity, comparison_id, seed, offset, limit,
                          coverage_incomplete, basemap, licence, excluded_rows):
    wells, water = waterbody_map_batch(_engine, comparison_id, seed, offset, limit, licence=licence,
                                        excluded_rows=excluded_rows)
    if not wells:
        return None, 0, 0
    view = build_waterbody_batch_map(wells, water, coverage_incomplete=coverage_incomplete, basemap=basemap,
                                    focus=bool(licence))
    return view.get_root().render(), len(wells), sum(row['observed_distance_m'] is not None for row in wells)


def shift_map_batch(step, batches):
    st.session_state.province_map_batch = (st.session_state.province_map_batch + step) % batches


@st.fragment
def show_comparison_map(engine, database_identity, summary, licence, basemap_default):
    st.subheader('ST37 wells and water features')
    if basemap_default:
        st.caption('The map displays well positions in WGS84. PostGIS measures straight-line distance in EPSG:3400 metres. '
                   'The precision of reported well positions and water geometry limits distance accuracy.')
    outside = audited_outside_rows(summary['st37_import_id'])
    well_count = summary['well_count'] - len(outside)
    if outside:
        st.caption(f'Alberta boundary check · {well_count:,} wells on or inside · {len(outside):,} reported positions outside. '
                   'Workbook records retains the original coordinates for review.')
    if not well_count:
        return
    if st.session_state.get('province_map_well_snapshot') != summary['st37_import_id']:
        st.session_state.province_map_well_snapshot = summary['st37_import_id']
        st.session_state.province_map_seed = randbits(32)
        st.session_state.province_map_batch = 0
    batches = (well_count + WELL_MAP_BATCH_SIZE - 1) // WELL_MAP_BATCH_SIZE
    page = st.session_state.province_map_batch
    if licence:
        tiles = st.container()
    else:
        previous, next_batch, tiles = st.columns([1, 1, 2], vertical_alignment='center')
        previous.button('Previous batch', key='province_map_previous', on_click=shift_map_batch,
                        args=(-1, batches), disabled=batches == 1)
        next_batch.button('Next batch', key='province_map_next', on_click=shift_map_batch,
                          args=(1, batches), disabled=batches == 1)
    basemap = tiles.checkbox('Show OpenStreetMap basemap (online)', value=basemap_default,
                             key='st37_inventory_basemap' if basemap_default else 'province_map_basemap')
    incomplete = summary['coverage_status'] == 'incomplete'
    try:
        with st.spinner('Loading well locations…'):
            html, count, matched = cached_comparison_map(
                engine, database_identity, summary['comparison_id'], st.session_state.province_map_seed,
                0 if licence else page * WELL_MAP_BATCH_SIZE, WELL_MAP_BATCH_SIZE, incomplete, basemap, licence, outside)
    except SQLAlchemyError:
        st.warning('This map batch could not be read from PostGIS.')
        return
    if html is None:
        if licence and outside:
            st.info('This reported position falls outside the Alberta boundary. Open Workbook records to review the original coordinates.')
        else:
            st.info('No stored well points in this batch.')
        return
    if not licence:
        st.caption(f'Batch {page + 1:,} of {batches:,} · Showing {count:,} of {well_count:,} wells · '
                   f'{matched:,} observed matches within 500 m')
    alt = ('Selected ST37 well and nearest observed water feature' if licence else
           'Current shuffled ST37 well batch and nearest observed water features')
    st.iframe(html, height=520, alt=alt)
    gray = 'unknown within 500 m' if incomplete else 'no feature within 500 m'
    st.caption(f'Well colors by stored distance: red ≤50 m, orange >50–100 m, yellow >100–250 m, '
               f'blue >250–500 m, gray {gray}. Teal shapes show the nearest accepted water features.')


def show_stored_comparison(engine, comparison_id, *, licence=None, basemap_default=False):
    database_identity = engine.url.render_as_string(hide_password=True)
    summary = cached_province_summary(engine, database_identity, comparison_id)
    feature = 'layer-107 stream line' if summary['scope'] == PROVINCE_STREAM_SCOPE else 'layer-72 polygon'
    st.caption(f'Full comparison · {summary["well_count"]:,} ST37 wells · {comparison_id}')
    if summary['coverage_status'] == 'incomplete':
        st.warning('Counts show matches to accepted features. Other wells may have unknown results because some records were quarantined.')
    if licence is None:
        licence = st.text_input('ST37 licence number', key='province_water_licence').strip()
    if licence:
        result = waterbody_result(engine, comparison_id, licence)
        if result is None:
            st.info('No matching licence in this comparison. Include any leading zeros.')
            return
        st.dataframe(pd.DataFrame([result]), hide_index=True, alt='Stored water proximity for the selected ST37 licence',
                     column_order=['well_licence_number', 'nearest_waterbody', 'observed_distance_m', 'result_state',
                                   'licensee_name', 'licence_status', 'legal_location', 'surface_latitude',
                                   'surface_longitude', 'coordinate_crs', 'nearest_source_feature_id',
                                   'feature_type_code', 'coverage_status'],
                     column_config={'well_licence_number': 'Well licence', 'nearest_waterbody': 'Water feature name',
                                    'observed_distance_m': st.column_config.NumberColumn('Observed distance (m)', format='%.2f'),
                                    'result_state': 'Coverage result'})
    show_comparison_map(engine, database_identity, summary, licence, basemap_default)
    st.dataframe(pd.DataFrame([
        {'Threshold (m)': metres, 'Observed matches': summary[f'within_{metres}']} for metres in THRESHOLDS
    ]), hide_index=True, alt=f'Observed ST37 matches to {feature} features by threshold')
    st.caption(f'{summary["unknown_within_500"]:,} wells with unknown 500 m results · '
               f'{summary["no_feature_within_500"]:,} with no {feature} within 500 m')
