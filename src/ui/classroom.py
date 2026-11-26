"""Streamlit views for the local ST37 preview and illustrative scenario."""
import os
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from src.contracts.spatial import CATEGORIES
from src.demo.data import (
    DEFAULT_PACKAGE, IMPORTED_WATER_MODE, SOURCE_CREDIT, dashboard_for, decode_package, json_bytes, read_package_bytes,
)
from src.demo.regions import REGION_IDS
from src.demo.spatial import WATER_PROVENANCE, selected_buffer
from src.exports.selection import FIELDS as EXPORT_FIELDS, csv_bytes, geojson_bytes, table_records
from src.spatial.classification import THRESHOLDS, classify_distance, compare_selections
from src.ui.map import ProximityLegend, buffer_group, build_map
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
PROJECTED_FIELDS = (*PREVIEW_FIELDS, 'distance_basis', *(field for field in EXPORT_FIELDS if field not in PREVIEW_FIELDS))
TABLE_LABELS = {
    'source_well_id': 'Well licence', 'region': 'Region', 'licensee_name': 'Licensee',
    'lsd_text': 'Legal location', 'status': 'Licence status',
    'source_latitude': 'Reported latitude', 'source_longitude': 'Reported longitude',
    'distance_m': 'Simulated distance (m)', 'band': 'Simulated proximity band',
    'matches_threshold': 'Within selected threshold', 'coverage_complete': 'Scenario coverage complete',
}
BASELINE_M = 500
FILTER_DEFAULTS = {
    'classroom_statuses': [], 'classroom_licence': '',
    'classroom_categories': ['water'],
}


@st.cache_data(max_entries=4, show_spinner=False)
def cached_package(contents: bytes) -> dict:
    return decode_package(contents)


@st.cache_data(max_entries=8, show_spinner=False)
def cached_dashboard(package: dict, region_ids: tuple[str, ...]) -> dict:
    return dashboard_for(package, region_ids)


def clear_filters(real_water: bool):
    for key, value in FILTER_DEFAULTS.items():
        st.session_state[key] = value
    st.session_state.classroom_threshold = BASELINE_M if real_water else 100
    st.session_state.classroom_matches_only = real_water


def select_well():
    st.session_state.classroom_selected = st.session_state.classroom_inspect


def clear_selection():
    st.session_state.classroom_selected = None


def show_classroom():
    path = Path(os.getenv('CLASSROOM_DEMO_PATH') or DEFAULT_PACKAGE)
    try:
        package = cached_package(read_package_bytes(path))
    except FileNotFoundError:
        st.info('Build the imported-water classroom package with scripts/prepare_classroom_demo.py or set CLASSROOM_DEMO_PATH to a prepared package.')
        return
    except PermissionError:
        st.error('Streamlit cannot read the classroom package. Check file permissions for the account running the app.')
        return
    except (OSError, ValueError, RuntimeError):
        st.error('The local classroom package could not be verified. Check the file or prepare it again.')
        return

    manifest = package['manifest']
    real_water = manifest['mode'] == IMPORTED_WATER_MODE
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
        clear_filters(real_water)
    try:
        dashboard = cached_dashboard(package, region_ids)
    except (ValueError, RuntimeError):
        st.error('The classroom geometry could not be prepared. Check the package’s coordinate evidence and CRS.')
        return

    projected = bool(manifest['coordinate_reference'])
    title = 'classroom demo with imported waterways' if real_water else ('illustrative classroom demo' if projected else 'ST37 well preview')
    st.subheader(f'{region_names[region]} · {title}')
    st.info(manifest['disclaimer'])
    st.caption(SOURCE_CREDIT)
    if real_water:
        st.caption('Water source · Government of Alberta Lake/River (20K) and Stream (20K) inventories')
    st.sidebar.header('Filters')
    wells = dashboard['wells']
    statuses = st.sidebar.multiselect('Licence status', sorted({
        well['status'] or MISSING for well in wells}), key='classroom_statuses')
    licence = st.sidebar.text_input('Well licence number', key='classroom_licence').strip().casefold()
    layer_labels = ({key: 'Imported waterways' if key == 'water' else f'{label} (synthetic)'
                     for key, label in CATEGORY_LABELS.items()} if real_water else CATEGORY_LABELS)
    if projected:
        categories = st.sidebar.multiselect('Environmental layers' if real_water else 'Synthetic environmental layers',
                                            sorted(CATEGORIES), format_func=layer_labels.__getitem__, key='classroom_categories')
        threshold = st.sidebar.segmented_control('Buffer distance', THRESHOLDS, required=True,
                                               format_func=lambda metres: f'{metres} m', key='classroom_threshold',
                                               help='A well matches when a selected feature is at or within this distance.') or BASELINE_M
        matches_only = st.sidebar.checkbox('Only show wells within the buffer', key='classroom_matches_only')
    else:
        categories, threshold, matches_only = [], BASELINE_M, False
    st.sidebar.button('Clear filters', on_click=clear_filters, args=(real_water,))

    population = [row for row in filtered_wells(dashboard, categories, threshold, statuses=statuses)
                  if licence in row['source_well_id'].casefold()]
    distance_basis = 'simulated'
    water_incomplete = any(source['coverage_status'] == 'incomplete' for source in manifest.get('water_sources', []))
    if real_water and 'water' in categories:
        distance_basis = 'imported_water' if categories == ['water'] else 'imported_water_and_simulated'
        if water_incomplete:
            st.warning('Imported water coverage is incomplete. A measured match uses accepted features. Wells without a match have unknown water proximity within 500 m.')
    for row in population:
        row['distance_basis'] = distance_basis if categories else None
        if distance_basis == 'imported_water' and row['observed_min_distance_m'] is not None:
            row['color'] = classify_distance(row['observed_min_distance_m'])['color']
    visible = [row for row in population if row['matches_threshold'] is True or not matches_only]
    metrics = st.columns(4 if projected else 3)
    metrics[0].metric('Regional candidates', dashboard['candidate_count'])
    metrics[1].metric('Sampled wells', len(wells))
    metrics[2].metric('Visible wells', len(visible))
    selection = {
        'package_id': package['package_id'], 'mode': manifest['mode'], 'regions': list(region_ids),
        'licence_statuses': statuses, 'licence_query': licence,
    }
    comparison = None
    map_bytes = None
    if projected:
        metric = {'simulated': 'Within simulated threshold', 'imported_water': 'Observed matches within threshold',
                  'imported_water_and_simulated': 'Matches within threshold'}[distance_basis]
        metrics[3].metric(metric, sum(row['matches_threshold'] is True for row in population))
        selection.update(categories=categories, threshold_m=threshold, matches_only=matches_only,
                         distance_basis=distance_basis if categories else None)
        if real_water and 'water' in categories:
            selection['water_coverage_status'] = 'incomplete' if water_incomplete else 'complete'
        baseline = [row for row in filtered_wells(dashboard, categories, BASELINE_M, statuses=statuses)
                    if licence in row['source_well_id'].casefold()]
        comparison = compare_selections(baseline, population)
        if matches_only and not visible:
            st.info(f'No observed well matches within {threshold} m for the current filters.')
        map_bytes = show_map(dashboard, visible, region, selection)
    show_details(visible, [row for row in dashboard['proximity'] if row['category'] in categories],
                 dashboard['features'], layer_labels, real_water)
    show_table(visible, projected, distance_basis)
    if comparison is not None:
        st.subheader('Simulated threshold comparison' if distance_basis == 'simulated' else 'Threshold comparison')
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
    extents = [dashboard['manifest']['config']['regions'][key]['bbox_wgs84'] for key in selection['regions']]
    bounds = [[min(extent[1] for extent in extents), min(extent[0] for extent in extents)],
              [max(extent[3] for extent in extents), max(extent[2] for extent in extents)]]
    notice = (f'Imported Alberta waterways · Other layers and their distances are synthetic · {SOURCE_CREDIT}'
              if dashboard['manifest']['mode'] == IMPORTED_WATER_MODE
              else f'Synthetic environmental features and simulated distances · {SOURCE_CREDIT}')
    distance_basis = selection['distance_basis']
    distance_label = {
        'imported_water': 'Distance to nearest accepted water feature',
        'imported_water_and_simulated': 'Imported water and simulated layers',
        'simulated': 'Simulated distance to selected layers',
        None: None,
    }[distance_basis]
    if distance_basis is None:
        unmatched = 'No layers selected'
    elif selection.get('water_coverage_status') == 'incomplete':
        unmatched = ('Unknown within 500 m' if distance_basis == 'imported_water'
                     else 'Unknown or no match within 500 m')
    else:
        unmatched = 'No match within 500 m'
    water_label = None
    if 'water' in selection['categories']:
        water_label = 'Simulated water feature' if distance_basis == 'simulated' else 'Accepted water feature'
    view = build_map(*view_args, basemap=basemap, notice=notice, bounds=bounds)
    ProximityLegend(distance_label, unmatched, water_label=water_label).add_to(view)
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
    if well is not None:
        st.caption(f'{threshold} m buffer around selected well {well["source_well_id"]}.')
    coverage = 'Imported water coverage is incomplete. ' if selection.get('water_coverage_status') == 'incomplete' else ''
    export_map = build_map(*view_args, basemap=basemap,
                           notice=f'{dashboard["manifest"]["disclaimer"]} {coverage}{SOURCE_CREDIT}', bounds=bounds)
    ProximityLegend(distance_label, unmatched, water_label=water_label).add_to(export_map)
    # streamlit-folium rewrites component IDs, including IDs on dynamic layers.
    if geometry is not None:
        buffer_group(geometry, threshold).add_to(export_map)
    return export_map.get_root().render().encode('utf-8')


def show_details(records: list[dict], proximity: list[dict], features: list[dict], layer_labels: dict, real_water: bool):
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
        st.subheader('Selected well · proximity' if real_water else 'Selected well · simulated proximity')
        names = {feature['source_feature_id']: feature['name'] for feature in features}
        st.dataframe(pd.DataFrame([
            {'Layer': layer_labels[row['category']], 'Nearest feature': names.get(row['nearest_feature_id']),
             'Distance (m)': row['distance_m'], 'Result': row['result_state']}
            for row in proximity if row['well_pk'] == selected
        ]), hide_index=True, alt='Distance from the selected well to each selected environmental layer')


def show_table(records: list[dict], projected: bool, distance_basis: str):
    st.subheader('Filtered wells')
    labels = TABLE_LABELS
    if distance_basis != 'simulated':
        observed = 'Observed water distance (m)' if distance_basis == 'imported_water' else 'Closest observed or simulated distance (m)'
        labels = {('observed_min_distance_m' if key == 'distance_m' else key):
                  observed if key == 'distance_m' else label for key, label in labels.items()}
        labels.update(band='Proximity band', coverage_complete='Coverage complete')
    fields = tuple(labels) if projected else tuple(labels)[:7]
    rows = pd.DataFrame(table_records(records, fields), columns=fields).rename(columns=labels)
    st.dataframe(rows, hide_index=True, alt='Filtered wells and proximity results for the selected layers')
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
                  'generator_seed': group['generator_seed'],
                  'imported_water_features': sum(f['provenance'] == WATER_PROVENANCE for f in group['features']),
                  'synthetic_features': sum(f['provenance'] != WATER_PROVENANCE for f in group['features'])}
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
