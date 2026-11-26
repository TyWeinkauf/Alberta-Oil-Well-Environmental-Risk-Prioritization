"""Explicit Streamlit actions for provincial hydrography and retained ST37 wells."""
import json
from datetime import datetime, timezone
from secrets import randbits
from uuid import UUID

import pandas as pd
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from src.config import ROOT
from src.db.st37 import (
    ST37_INVENTORY_OPTION_LIMIT, ST37_INVENTORY_PAGE_SIZE, import_st37_workbook, st37_import_snapshots,
    st37_inventory_count, st37_inventory_filter_options, st37_inventory_page,
)
from src.db.waterbodies import (
    WELL_MAP_BATCH_SIZE, compare_st37_waterbodies, find_waterbody_comparison, st37_water_comparisons, waterbody_buffer_count,
    st37_workbook_water_results, waterbody_comparison_summary, waterbody_map_batch, waterbody_result,
    waterbody_workflow_snapshots,
)
from src.db.workflow import WorkflowBusy
from src.demo.spatial import selected_buffer
from src.sources.st37 import FIELDS as ST37_FIELDS
from src.sources.waterbodies import PROVINCE_STREAM_SCOPE, import_province_streams, import_province_waterbodies
from src.spatial.classification import THRESHOLDS, classify_distance
from src.ui.map import buffer_group, build_waterbody_batch_map

ST37_WORKBOOK = ROOT / 'aida-final-project-tyler-weinkauf/courses/AIDA-1145/data/ST37_SH.xlsx'
ST37_RAW_ROOT = ROOT / 'data/raw/st37'
ST37_ALBERTA_BOUNDARY_QA = ROOT / 'docs/evidence/st37_alberta_boundary_2026-11-23.json'
WORKBOOK_WATER_BANDS = {
    'within_50m': '≤50 m', 'within_100m': '>50–100 m', 'within_250m': '>100–250 m',
    'within_500m': '>250–500 m', 'none_within_500m': 'No match within 500 m', 'unavailable': 'Unavailable',
}
WORKBOOK_FILTER_LABELS = {
    'licence_status': 'Licence status',
    'energy_development_category': 'Energy development category',
}
MAP_FILTER_LABELS = {'licence_status': 'Licence status'}


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
    requested = st.button('Import ST37 wells', key='import_st37_workbook', type='primary',
                          disabled=st.session_state.busy or not workbook_exists)
    if workbook_exists:
        st.caption(f'Workbook {ST37_WORKBOOK.name} from the course data folder.')
    else:
        st.info('Place ST37_SH.xlsx in the AIDA 1145 data folder to enable the import.')
    if requested:
        result = run_action(
            'Import ST37 wells',
            lambda progress: import_st37_workbook(engine, ST37_WORKBOOK, ST37_RAW_ROOT, progress=progress),
            lambda row: f'ST37 inventory ready · {row["accepted"]:,} accepted wells',
        )
        if result:
            st.session_state[snapshot_key] = UUID(result['import_id'])


def workbook_water_columns(result: dict | None) -> dict:
    distance = result['observed_distance_m'] if result is not None else None
    if result is None:
        band = 'unavailable'
    elif distance is None:
        band = 'none_within_500m'
    else:
        band = classify_distance(distance)['band']
    return {'Observed water distance (m)': distance, 'Water proximity band': WORKBOOK_WATER_BANDS[band]}


@st.cache_data(max_entries=24, show_spinner=False)
def cached_st37_filter_options(_engine, database_identity, snapshot_id, field, search=''):
    return st37_inventory_filter_options(_engine, snapshot_id, field, search)


@st.cache_data(max_entries=32, show_spinner=False)
def cached_workbook_match_count(_engine, database_identity, snapshot_id, filters, comparison_ids):
    return st37_inventory_count(_engine, snapshot_id, filters, water_comparison_ids=comparison_ids)


def st37_attribute_filters(engine, database_identity, snapshot_id, fields_and_columns, key_prefix):
    filters = {}
    for (field, label), column in fields_and_columns:
        key = f'{key_prefix}_{field}_{snapshot_id}'
        options = cached_st37_filter_options(engine, database_identity, snapshot_id, field)
        if len(options) > ST37_INVENTORY_OPTION_LIMIT:
            search = column.text_input(f'Search {label.lower()}', key=f'{key}_search', live='300ms').strip()
            found = cached_st37_filter_options(engine, database_identity, snapshot_id, field, search) if search else []
            if len(found) > ST37_INVENTORY_OPTION_LIMIT:
                column.caption('Narrow the search to see all matching options.')
            blank = {''} if '' in options else set()
            options = sorted(set(found[:ST37_INVENTORY_OPTION_LIMIT]) | set(st.session_state.get(key, ())) | blank)
        values = column.multiselect(label, options, key=key, format_func=lambda value: value or '(Blank)', placeholder='All')
        if values:
            filters[field] = sorted(values)
    return filters


def workbook_filters(engine, database_identity, snapshot_id, comparison_ids):
    columns = st.columns(len(WORKBOOK_FILTER_LABELS) + 1)
    filters = st37_attribute_filters(engine, database_identity, snapshot_id,
                                     zip(WORKBOOK_FILTER_LABELS.items(), columns), 'st37_filter')
    bands = columns[-1].multiselect(
        'Water proximity band', list(WORKBOOK_WATER_BANDS) if comparison_ids else ['unavailable'],
        key=f'st37_filter_water_band_{snapshot_id}', format_func=WORKBOOK_WATER_BANDS.__getitem__, placeholder='All',
    )
    if bands:
        filters['water_band'] = bands
    return filters


def inventory_licence():
    return st.text_input('Well licence number', key='st37_inventory_licence',
                         help='Enter the complete licence, including any leading zeros.').strip()


def clear_st37_map_filters(snapshot_id, default_layer_id):
    for field in MAP_FILTER_LABELS:
        key = f'st37_map_{field}_{snapshot_id}'
        st.session_state[key] = []
        st.session_state.pop(f'{key}_search', None)
    st.session_state.st37_inventory_licence = ''
    st.session_state.st37_inventory_water = default_layer_id
    st.session_state.st37_map_threshold = THRESHOLDS[-1]
    st.session_state.st37_map_matches_only = True
    st.session_state.province_map_batch = 0


def map_buffer_controls(licence):
    st.session_state.setdefault('st37_map_threshold', THRESHOLDS[-1])
    st.session_state.setdefault('st37_map_matches_only', True)
    threshold = st.segmented_control('Buffer distance', THRESHOLDS, required=True,
                                     format_func=lambda metres: f'{metres} m', key='st37_map_threshold') or THRESHOLDS[-1]
    matches_only = st.checkbox('Only show wells within the buffer', key='st37_map_matches_only',
                               disabled=bool(licence), help='Filters the shuffled batches by observed distance to the selected water layer.')
    return threshold, matches_only


def show_st37_water_map(engine, snapshot_id, comparisons):
    database_identity = engine.url.render_as_string(hide_password=True)
    with st.sidebar:
        st.header('Filters')
        fields = [(field, st.sidebar) for field in MAP_FILTER_LABELS.items()]
        filters = st37_attribute_filters(engine, database_identity, snapshot_id, fields, 'st37_map')
        licence = inventory_licence()
        water = snapshot_select('Imported water layer', 'st37_inventory_water', comparisons, water_choice)
        buffer = map_buffer_controls(licence)
        st.button('Clear filters', key='st37_map_clear', on_click=clear_st37_map_filters,
                  args=(snapshot_id, comparisons[0]['import_id']))
    show_stored_comparison(engine, water['comparison_id'], licence=licence, basemap_default=True,
                           filters=filters, buffer=buffer)


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
    try:
        comparisons = st37_water_comparisons(engine, snapshot['import_id']) if snapshot['coordinate_crs'] else []
    except SQLAlchemyError:
        comparisons = []
        st.warning('The stored water comparisons could not be read.')
    if comparisons:
        view = st.radio('Inventory view', ['Water proximity map', 'Workbook records'], horizontal=True,
                        key='st37_inventory_view')
        if view == 'Water proximity map':
            try:
                show_st37_water_map(engine, snapshot['import_id'], comparisons)
            except (SQLAlchemyError, ValueError):
                st.warning('The selected water comparison could not be read from PostGIS.')
            return
    elif snapshot['coordinate_crs']:
        st.caption('Create a stored water comparison with `scripts/compare_st37_waterbodies.py` to enable the map.')
    else:
        st.caption('The water proximity map requires a documented workbook coordinate CRS.')
    licence = inventory_licence()
    latest_by_layer: dict[str, UUID] = {}
    for comparison in comparisons:
        latest_by_layer.setdefault(comparison['scope'], comparison['comparison_id'])
    comparison_ids = tuple(latest_by_layer.values())
    database_identity = engine.url.render_as_string(hide_password=True)
    try:
        filters = workbook_filters(engine, database_identity, snapshot['import_id'], comparison_ids)
        matched_count = records
        if filters and not licence:
            matched_count = cached_workbook_match_count(engine, database_identity, snapshot['import_id'], filters, comparison_ids)
    except SQLAlchemyError:
        st.error('The workbook filters could not be read from PostgreSQL.')
        return
    page_key = f'st37_inventory_page_{snapshot["import_id"]}'
    scope = (snapshot['import_id'], licence, comparison_ids,
             tuple((field, tuple(sorted(values))) for field, values in filters.items()))
    if st.session_state.get('st37_workbook_page_scope') != scope:
        st.session_state.st37_workbook_page_scope = scope
        st.session_state[page_key] = 1
    offset = 0
    if not licence:
        if not matched_count:
            st.info('No workbook records match the selected filters.')
            return
        last_page = (matched_count + ST37_INVENTORY_PAGE_SIZE - 1) // ST37_INVENTORY_PAGE_SIZE
        page = st.number_input('Page', min_value=1, max_value=last_page, step=1, key=page_key)
        offset = (page - 1) * ST37_INVENTORY_PAGE_SIZE
    try:
        rows = st37_inventory_page(engine, snapshot['import_id'], offset=offset, licence=licence, filters=filters,
                                   water_comparison_ids=comparison_ids)
    except SQLAlchemyError:
        st.error('The selected ST37 rows could not be read from PostgreSQL.')
        return
    if not rows:
        if filters:
            st.info('No workbook records match the licence and selected filters.')
        else:
            st.info('No rows match this selection. Enter the full licence number, including any leading zeros.')
        return
    if licence:
        st.caption(f'Showing up to {ST37_INVENTORY_PAGE_SIZE:,} exact licence matches.')
    else:
        page_label = 'matching workbook records' if filters else 'in workbook order'
        st.caption(f'Rows {offset + 1:,}–{offset + len(rows):,} of {matched_count:,} {page_label}.')
    proximity = {}
    if comparison_ids:
        try:
            proximity = st37_workbook_water_results(engine, snapshot['import_id'],
                                                   [row['source_row'] for row in rows], comparison_ids)
            st.caption('Water columns use the nearest accepted match within 500 m from the latest stored comparison for each available layer.')
        except SQLAlchemyError:
            st.warning('Water proximity could not be read for this page.')
    outside = audited_outside_rows(snapshot['import_id'])
    table = [{
        'Workbook row': row['source_row'],
        'Well_Licence_Number': row['raw_payload']['Well_Licence_Number'],
        **workbook_water_columns(proximity.get(row['source_row'])),
        **{field: row['raw_payload'][field] for field in ST37_FIELDS
           if field not in ('Well_Licence_Number', 'Licensee')},
        'Validation errors': ', '.join(row['validation_errors']),
        'Quality warnings': ', '.join(row['quality_warnings']),
        **({'Boundary review': 'Reported position outside Alberta' if row['source_row'] in outside else ''}
           if outside else {}),
    } for row in rows]
    records_table = pd.DataFrame(table).astype({'Observed water distance (m)': 'Float64'})
    st.dataframe(records_table, hide_index=True, alt='ST37 workbook records and observed water proximity',
                 column_config={
                     'Well_Licence_Number': 'Well licence', 'Licence_Status': 'Licence status',
                     'Energy_Devlpmt_Category_Type': 'Energy development category',
                     'Licence_Surface_Location_Label': 'Legal location', 'SH_Actual_Latitude': 'Reported latitude',
                     'SH_Actual_Longitude': 'Reported longitude',
                     'Observed water distance (m)': st.column_config.NumberColumn(
                         format='%.2f', help='Nearest observed distance in EPSG:3400 metres, displayed to two decimal places.'),
                 })


def water_choice(row):
    layer = 'Stream lines' if row['scope'] == PROVINCE_STREAM_SCOPE else 'Waterbody polygons'
    return (f'{layer} · {row["feature_count"]:,} · {row["coverage_status"]} coverage · '
            f'{row["imported_at"].astimezone(timezone.utc):%Y-%m-%d %H:%M UTC} · {str(row["import_id"])[:8]}')


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
                          coverage_incomplete, basemap, licence, excluded_rows, threshold, max_distance, filters):
    wells, water = waterbody_map_batch(_engine, comparison_id, seed, offset, limit, licence=licence,
                                        excluded_rows=excluded_rows, max_distance_m=max_distance, filters=filters)
    if not wells:
        return None, 0, 0
    view = build_waterbody_batch_map(wells, water, coverage_incomplete=coverage_incomplete, basemap=basemap,
                                    focus=bool(licence))
    if licence:
        buffer_group(selected_buffer(wells[0], threshold), threshold).add_to(view)
    matched = sum(row['observed_distance_m'] is not None and row['observed_distance_m'] <= threshold for row in wells)
    return view.get_root().render(), len(wells), matched


@st.cache_data(max_entries=24, show_spinner=False)
def cached_map_count(_engine, database_identity, comparison_id, max_distance, excluded_rows, filters):
    return waterbody_buffer_count(_engine, comparison_id, max_distance, excluded_rows, filters=filters)


def shift_map_batch(step, batches):
    st.session_state.province_map_batch = (st.session_state.province_map_batch + step) % batches


@st.fragment
def show_comparison_map(engine, database_identity, summary, licence, basemap_default, filters, buffer):
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
    threshold, matches_only = buffer if buffer is not None else map_buffer_controls(licence)
    max_distance = threshold if matches_only and not licence else None
    if st.session_state.get('province_map_well_snapshot') != summary['st37_import_id']:
        st.session_state.province_map_well_snapshot = summary['st37_import_id']
        st.session_state.province_map_seed = randbits(32)
        st.session_state.province_map_batch = 0
    if not licence:
        batch_filter = (summary['comparison_id'] if max_distance is not None else None, max_distance, filters)
        if st.session_state.get('province_map_batch_filter') != batch_filter:
            st.session_state.province_map_batch_filter = batch_filter
            st.session_state.province_map_batch = 0
    try:
        if not licence and (max_distance is not None or filters):
            well_count = cached_map_count(engine, database_identity, summary['comparison_id'], max_distance, outside, filters)
    except SQLAlchemyError:
        st.warning('The map match count could not be read from PostGIS.')
        return
    if not well_count:
        if filters:
            suffix = f' within {threshold} m' if max_distance is not None else ''
            st.info(f'No wells match the selected filters{suffix}.')
        else:
            st.info(f'No observed well matches within {threshold} m for this water layer.')
        return
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
                0 if licence else page * WELL_MAP_BATCH_SIZE, WELL_MAP_BATCH_SIZE, incomplete, basemap,
                licence, outside, threshold, max_distance, filters)
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
                   f'{matched:,} observed matches within {threshold} m')
    else:
        st.caption(f'{threshold} m buffer around selected well {licence}.')
    alt = ('Selected ST37 well and nearest observed water feature' if licence else
           'Current shuffled ST37 well batch and nearest observed water features')
    st.iframe(html, height=520, alt=alt)


def show_stored_comparison(engine, comparison_id, *, licence=None, basemap_default=False, filters=None, buffer=None):
    database_identity = engine.url.render_as_string(hide_password=True)
    summary = cached_province_summary(engine, database_identity, comparison_id)
    feature = 'layer-107 stream line' if summary['scope'] == PROVINCE_STREAM_SCOPE else 'layer-72 polygon'
    st.caption(f'Full comparison · {summary["well_count"]:,} ST37 wells · {comparison_id}')
    if summary['coverage_status'] == 'incomplete':
        st.warning('Counts show matches to accepted features. Other wells may have unknown results because some records were quarantined.')
    if licence is None:
        licence = st.text_input('ST37 licence number', key='province_water_licence').strip()
    if licence:
        result = waterbody_result(engine, comparison_id, licence, filters=filters)
        if result is None:
            if filters:
                st.info('No well matches the exact licence and selected filters.')
            else:
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
    show_comparison_map(engine, database_identity, summary, licence, basemap_default, filters, buffer)
    if filters:
        st.caption('Threshold totals for the full comparison')
    st.dataframe(pd.DataFrame([
        {'Threshold (m)': metres, 'Observed matches': summary[f'within_{metres}']} for metres in THRESHOLDS
    ]), hide_index=True, alt=f'Observed ST37 matches to {feature} features by threshold')
    st.caption(f'{summary["unknown_within_500"]:,} wells with unknown 500 m results · '
               f'{summary["no_feature_within_500"]:,} with no {feature} within 500 m')
