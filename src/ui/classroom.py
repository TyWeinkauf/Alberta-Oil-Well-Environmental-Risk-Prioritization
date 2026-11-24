"""Streamlit views for the local ST37 preview and illustrative scenario."""
import os
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from src.contracts.spatial import CATEGORIES
from src.demo.data import (
    DEFAULT_PACKAGE, SOURCE_CREDIT, dashboard_for, decode_package, json_bytes, read_package_bytes,
)
from src.demo.regions import REGION_IDS
from src.demo.spatial import selected_buffer
from src.exports.selection import FIELDS as EXPORT_FIELDS, csv_bytes, geojson_bytes, table_records
from src.spatial.classification import THRESHOLDS, compare_selections
from src.ui.map import build_map
from src.ui.model import filtered_wells, map_selection

MISSING = 'Not available from this source'
CATEGORY_LABELS = {
    'water': 'Water', 'wetland': 'Wetland', 'protected_area': 'Protected area',
    'critical_habitat': 'Critical habitat', 'esa': 'Significance area',
}
PREVIEW_FIELDS = (
    'run_id', 'region', 'source_well_id', 'licensee_name', 'lsd_text', 'status',
    'source_latitude', 'source_longitude', 'source_crs', 'source_row',
    'Licence_Status_Date', 'Ground_Elevation', 'Spud_Date',
    'Most_Recent_Final_Drill_Date', 'Energy_Devlpmt_Category_Type', 'quality_warnings',
    'mode', 'well_provenance', 'environment_provenance', 'source_credit', 'disclaimer',
)
PROJECTED_FIELDS = PREVIEW_FIELDS + tuple(field for field in EXPORT_FIELDS if field not in PREVIEW_FIELDS)
TABLE_LABELS = {
    'source_well_id': 'Well licence', 'region': 'Region', 'licensee_name': 'Licensee',
    'lsd_text': 'Legal location', 'status': 'Licence status',
    'source_latitude': 'Reported latitude', 'source_longitude': 'Reported longitude',
    'distance_m': 'Simulated distance (m)', 'band': 'Simulated proximity band',
    'matches_threshold': 'Within selected threshold', 'coverage_complete': 'Scenario coverage complete',
}
BASELINE_M = 500
FILTER_DEFAULTS = {
    'classroom_companies': [], 'classroom_statuses': [], 'classroom_licence': '',
    'classroom_categories': ['water'], 'classroom_threshold': 100, 'classroom_matches_only': False,
}


@st.cache_data(max_entries=4, show_spinner=False)
def cached_package(contents: bytes) -> dict:
    return decode_package(contents)


@st.cache_data(max_entries=8, show_spinner=False)
def cached_dashboard(package: dict, region_ids: tuple[str, ...]) -> dict:
    return dashboard_for(package, region_ids)


def clear_filters():
    for key, value in FILTER_DEFAULTS.items():
        st.session_state[key] = value


def select_well():
    st.session_state.classroom_selected = st.session_state.classroom_inspect


def clear_selection():
    st.session_state.classroom_selected = None


def show_classroom():
    path = Path(os.getenv('CLASSROOM_DEMO_PATH') or DEFAULT_PACKAGE)
    try:
        package = cached_package(read_package_bytes(path))
    except FileNotFoundError:
        st.info('Prepare a classroom package with scripts/prepare_classroom_demo.py or set CLASSROOM_DEMO_PATH to an existing package.')
        return
    except (OSError, ValueError, RuntimeError):
        st.error('The local classroom package could not be verified. Check the file or prepare it again.')
        return

    manifest = package['manifest']
    region_names = {key: entry['name'] for key, entry in manifest['config']['regions'].items()}
    region_names['both'] = 'Both'
    region = st.sidebar.radio('Classroom region', [*REGION_IDS, 'both'],
                              format_func=region_names.__getitem__, key='classroom_region')
    region_ids = REGION_IDS if region == 'both' else (region,)
    scope = (package['package_id'], region)
    if st.session_state.get('classroom_scope') != scope:
        st.session_state.classroom_scope = scope
        st.session_state.classroom_map_event = None
        clear_selection()
        clear_filters()
    try:
        dashboard = cached_dashboard(package, region_ids)
    except (ValueError, RuntimeError):
        st.error('The classroom geometry could not be prepared. Check the package’s coordinate evidence and CRS.')
        return

    projected = bool(manifest['coordinate_reference'])
    st.subheader(f'{region_names[region]} · {"illustrative classroom demo" if projected else "ST37 well preview"}')
    st.info(manifest['disclaimer'])
    st.caption(SOURCE_CREDIT)
    st.sidebar.header('Filters')
    wells = dashboard['wells']
    companies = st.sidebar.multiselect('Company (licensee)', sorted({
        well['licensee_name'] or MISSING for well in wells}), key='classroom_companies')
    statuses = st.sidebar.multiselect('Licence status', sorted({
        well['status'] or MISSING for well in wells}), key='classroom_statuses')
    licence = st.sidebar.text_input('Well licence number', key='classroom_licence').strip().casefold()
    if projected:
        categories = st.sidebar.multiselect('Synthetic environmental layers', sorted(CATEGORIES),
                                            format_func=CATEGORY_LABELS.__getitem__, key='classroom_categories')
        threshold = st.sidebar.selectbox('Distance threshold (m)', THRESHOLDS, key='classroom_threshold')
        matches_only = st.sidebar.checkbox('Only wells within threshold', key='classroom_matches_only')
    else:
        categories, threshold, matches_only = [], BASELINE_M, False
    st.sidebar.button('Clear filters', on_click=clear_filters)

    population = [row for row in filtered_wells(dashboard, categories, threshold, companies, statuses)
                  if licence in row['source_well_id'].casefold()]
    visible = [row for row in population if row['matches_threshold'] is True or not matches_only]
    metrics = st.columns(4 if projected else 3)
    metrics[0].metric('Regional candidates', dashboard['candidate_count'])
    metrics[1].metric('Sampled wells', len(wells))
    metrics[2].metric('Visible wells', len(visible))
    selection = {
        'package_id': package['package_id'], 'mode': manifest['mode'], 'regions': list(region_ids),
        'companies': companies, 'licence_statuses': statuses, 'licence_query': licence,
    }
    comparison = None
    map_bytes = None
    if projected:
        metrics[3].metric('Within simulated threshold', sum(row['matches_threshold'] is True for row in population))
        selection.update(categories=categories, threshold_m=threshold, matches_only=matches_only)
        baseline = [row for row in filtered_wells(dashboard, categories, BASELINE_M, companies, statuses)
                    if licence in row['source_well_id'].casefold()]
        comparison = compare_selections(baseline, population)
        map_bytes = show_map(dashboard, visible, region, selection)
    show_details(visible, [row for row in dashboard['proximity'] if row['category'] in categories])
    show_table(visible, projected)
    if comparison is not None:
        st.subheader('Simulated threshold comparison')
        st.write(f'{BASELINE_M} m baseline: {comparison["baseline_matched"]} matches. '
                 f'{threshold} m selection: {comparison["changed_matched"]} matches. '
                 f'{comparison["changed_count"]} wells changed.')
        if comparison['changed_well_ids']:
            st.text('Changed well licences: ' + ', '.join(comparison['changed_well_ids']))
    comparison_export = None if comparison is None else {'baseline_m': BASELINE_M, 'changed_m': threshold, **comparison}
    show_exports(visible, package, selection, comparison_export, map_bytes)


def show_map(dashboard: dict, records: list[dict], region: str, selection: dict) -> bytes:
    basemap = st.checkbox('Show OpenStreetMap basemap (online)', key='classroom_basemap')
    selection['openstreetmap'] = basemap
    threshold = selection['threshold_m']
    visible_keys = {row['well_pk'] for row in records}
    map_scope = (dashboard['run_id'], region, visible_keys, tuple(selection['categories']), basemap)
    if st.session_state.get('classroom_map_scope') != map_scope:
        st.session_state.classroom_map_scope = map_scope
        st.session_state.classroom_map_event = None
    view_args = (records, dashboard['features'], selection['categories'])
    notice = f'Synthetic environmental features and simulated distances · {SOURCE_CREDIT}'
    view = build_map(*view_args, basemap=basemap, notice=notice)
    well = next((row for row in records if row['well_pk'] == st.session_state.classroom_selected), None)
    geometry = selected_buffer(well, threshold) if well is not None else None
    event = st_folium(
        view, key=f'classroom-map-{dashboard["run_id"]}-{region}', width=None, height=480,
        returned_objects=['last_object_clicked_popup', 'last_object_clicked_count'],
        feature_group_to_add=buffer_group(geometry, threshold),
    )
    selected, signature = map_selection(event, visible_keys, st.session_state.classroom_map_event)
    st.session_state.classroom_map_event = signature
    if selected is not None and selected != st.session_state.classroom_selected:
        st.session_state.classroom_selected = selected
        st.rerun()
    st.caption('Simulated bands: red ≤50 m, orange >50–100 m, yellow >100–250 m, '
               'blue >250–500 m, gray no match or unknown. Distances use EPSG:3400 metres.')
    if well is not None:
        st.caption(f'{threshold} m buffer around selected well {well["source_well_id"]}.')
    export_map = build_map(*view_args, basemap=basemap, notice=f'{dashboard["manifest"]["disclaimer"]} {SOURCE_CREDIT}')
    # streamlit-folium rewrites component IDs, including IDs on dynamic layers.
    if geometry is not None:
        buffer_group(geometry, threshold).add_to(export_map)
    return export_map.get_root().render().encode('utf-8')


def buffer_group(geometry: dict | None, threshold: int) -> folium.FeatureGroup:
    group = folium.FeatureGroup(name='Selected well buffer')
    if geometry is not None:
        folium.GeoJson(geometry, tooltip=f'{threshold} m selected well buffer',
                       style_function=lambda _: {'color': '#202027', 'weight': 2, 'dashArray': '5 4',
                                                 'fillOpacity': 0.06}).add_to(group)
    return group


def show_details(records: list[dict], proximity: list[dict]):
    by_key = {row['well_pk']: row for row in records}
    selected = st.session_state.classroom_selected
    st.session_state.classroom_inspect = selected if selected in by_key else None
    st.selectbox('Inspect a well', [None, *by_key], key='classroom_inspect', on_change=select_well,
                 format_func=lambda key: by_key[key]['source_well_id'] if key is not None else 'Choose a licence')
    if selected is None:
        return
    if selected not in by_key:
        st.info('Selected well is outside the current filters.')
        st.button('Clear selection', on_click=clear_selection)
        return
    well = by_key[selected]
    st.subheader(f'ST37 well {well["source_well_id"]}')
    labels = {
        'Licensee': 'Licensee', 'Legal location': 'Licence_Surface_Location_Label',
        'Licence status': 'Licence_Status', 'Licence status date': 'Licence_Status_Date',
        'Ground elevation': 'Ground_Elevation', 'Spud date': 'Spud_Date',
        'Most recent final drill date': 'Most_Recent_Final_Drill_Date',
        'Development category': 'Energy_Devlpmt_Category_Type',
        'Reported latitude': 'SH_Actual_Latitude', 'Reported longitude': 'SH_Actual_Longitude',
    }
    st.dataframe(pd.DataFrame([
        {'ST37 attribute': label, 'Source value': well['raw'][field] or MISSING}
        for label, field in labels.items()
    ]), hide_index=True, alt='Reported attributes of the selected ST37 well')
    st.caption(f'Coordinate datum: {well["source_crs"] or "pending"}. UWI and verified operator: {MISSING}.')
    if proximity:
        st.subheader('Selected well · simulated proximity')
        st.dataframe(pd.DataFrame([
            {'Synthetic layer': CATEGORY_LABELS[row['category']], 'Nearest synthetic feature': row['nearest_feature_id'],
             'Simulated distance (m)': row['distance_m'], 'Scenario result': row['result_state']}
            for row in proximity if row['well_pk'] == selected
        ]), hide_index=True, alt='Distance from the selected well to each synthetic layer')


def show_table(records: list[dict], projected: bool):
    st.subheader('Filtered wells')
    fields = tuple(TABLE_LABELS) if projected else tuple(TABLE_LABELS)[:7]
    rows = pd.DataFrame(table_records(records, fields), columns=fields).rename(columns=TABLE_LABELS)
    st.dataframe(rows, hide_index=True, alt='Filtered well records and available simulated proximity results')
    if not records:
        st.info('No wells match the current filters.')


def show_exports(records: list[dict], package: dict, selection: dict, comparison: dict | None,
                 map_bytes: bytes | None):
    st.subheader('Export current selection')
    projected = map_bytes is not None
    fields = PROJECTED_FIELDS if projected else PREVIEW_FIELDS
    # Retain the exact workbook values alongside mapped fields.
    rows = [{**row['raw'], **row, 'source_row': row['well_pk']} for row in records]
    manifest = {
        **package['manifest'], 'package_id': package['package_id'], 'selection': selection,
        'count': len(records), 'well_licences': [row['source_well_id'] for row in records],
        'threshold_comparison': comparison,
        'regions': {
            key: {'candidates': group['candidate_count'], 'sampled': len(group['wells']),
                  'generator_seed': group['generator_seed'], 'synthetic_features': len(group['features'])}
            for key, group in package['regions'].items() if key in selection['regions']
        },
    }
    columns = st.columns(4 if projected else 2)
    columns[0].download_button('Download CSV', csv_bytes(rows, fields), 'classroom_wells.csv',
                               'text/csv', on_click='ignore')
    columns[1].download_button('Download manifest', json_bytes(manifest), 'classroom_manifest.json',
                               'application/json', on_click='ignore')
    if projected:
        columns[2].download_button('Download GeoJSON', geojson_bytes(rows, selection, fields),
                                   'classroom_wells.geojson', 'application/geo+json', on_click='ignore')
        columns[3].download_button('Download map HTML', map_bytes, 'classroom_map.html',
                                   'text/html', on_click='ignore')
