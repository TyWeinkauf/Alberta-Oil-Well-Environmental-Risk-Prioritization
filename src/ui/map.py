"""Folium markers carry stable primary keys; vendored assets support offline use."""
import base64
import html
from functools import lru_cache
from typing import cast

import folium
from branca.element import Element, Figure

from src.config import ROOT
from src.spatial.classification import classify_distance

SCENARIO_COLORS = {
    'water': '#247ba0', 'wetland': '#087e66', 'protected_area': '#527629',
    'critical_habitat': '#8849a7', 'esa': '#9b521e',
}
WELL_COLORS = {'red': '#b91c1c', 'orange': '#c2410c', 'yellow': '#ca8a04', 'blue': '#1d4ed8', 'gray': '#64748b'}


def popup_text(value: str) -> str:
    # Folium places popup/tooltip HTML in JavaScript template literals.
    return html.escape(value).replace('`','&#96;').replace('$','&#36;').replace('\\','&#92;')


@lru_cache(maxsize=8)
def asset_uri(relative_path: str, mime: str) -> str:
    return f'data:{mime};base64,'+base64.b64encode((ROOT/relative_path).read_bytes()).decode()


def leaflet_view(center: list[float], zoom: int, basemap: bool, *, prefer_canvas: bool = False) -> folium.Map:
    view = folium.Map(location=center, zoom_start=zoom, tiles=None, control_scale=True, prefer_canvas=prefer_canvas)
    # Do not load third-party CDNs on every render; these same assets work in exported HTML.
    view.default_js = [('leaflet',asset_uri('vendor/leaflet/leaflet.js','text/javascript')),
                       ('jquery',asset_uri('vendor/jquery/jquery.min.js','text/javascript'))]
    view.default_css = [('leaflet_css',asset_uri('vendor/leaflet/leaflet.css','text/css'))]
    if basemap:
        folium.TileLayer('OpenStreetMap').add_to(view)
    return view


def build_map(records: list[dict], features: list[dict], categories: list[str], *, basemap: bool = False,
              overlays: bool = True, notice: str | None = None) -> folium.Map:
    center = ([sum(r['latitude'] for r in records)/len(records),sum(r['longitude'] for r in records)/len(records)]
              if records else [53.5,-114])
    view = leaflet_view(center, 12, basemap)
    if notice:
        cast(Figure, view.get_root()).html.add_child(Element(
            '<aside style="position:absolute;z-index:999;left:48px;right:8px;top:8px;'
            'padding:6px 9px;background:white;color:#222;font:12px sans-serif">'
            f'{html.escape(notice)}</aside>'))
    if overlays:
        for feature in features:
            if feature['feature_type'] in categories:
                illustrative = feature.get('provenance') == 'synthetic_environment'
                color = SCENARIO_COLORS[feature['feature_type']] if illustrative else '#247ba0'
                folium.GeoJson(feature['geometry'],name=feature['source_feature_id'],
                    tooltip=popup_text(feature['name']) if illustrative else None,
                    style_function=lambda _, feature_color=color: {
                        'color':feature_color,'weight':2,'fillOpacity':0.12}).add_to(view)
    for row in records:
        identifier = popup_text(row['source_well_id'])
        company = popup_text(row['licensee_name'] or 'Not available from this source')
        # streamlit-folium returns innerText, so attributes/hidden text are lost.
        # A small visible reference survives the bridge without using coordinates.
        token = f'<small>Record reference: {row["well_pk"]}</small><br>'
        source = '<br>Actual ST37 well · simulated surroundings' if notice else ''
        popup = (f'<section data-well-key="{row["well_pk"]}">{token}<strong>{identifier}</strong>'
                 f'<br>{company}{source}<br>View details below the map</section>')
        # Fixed palette from the shared classifier; no untrusted CSS is inserted.
        color = WELL_COLORS[row['color']]
        icon = folium.DivIcon(html=f'<span style="display:block;background:{color};width:18px;height:18px;'
                                  'border:2px solid white;border-radius:50%;box-shadow:0 1px 5px #333"></span>',
                              icon_size=(22,22),icon_anchor=(11,11))
        folium.Marker([row['latitude'],row['longitude']],popup=folium.Popup(popup,max_width=300),
                      tooltip=identifier,title=row['source_well_id'],icon=icon).add_to(view)
    if records:
        view.fit_bounds([[r['latitude'],r['longitude']] for r in records],padding=(35,35),max_zoom=18)
    return view


def build_waterbody_batch_map(wells: list[dict], water: list[dict], *,
                              coverage_incomplete: bool, basemap: bool, focus: bool = False) -> folium.Map:
    view = leaflet_view([54.5, -115], 5, basemap, prefer_canvas=True)
    feature_labels = {row['source_feature_id']: popup_text(row['name'] or f'Feature {row["source_feature_id"]}')
                      for row in water}
    if water:
        folium.GeoJson({'type': 'FeatureCollection', 'features': [
            {'type': 'Feature', 'id': row['source_feature_id'], 'geometry': row['geometry'],
             'properties': {'name': feature_labels[row['source_feature_id']]}}
            for row in water
        ]}, style_function=lambda _: {'color': '#247ba0', 'weight': 2, 'fillOpacity': 0.2},
            tooltip=folium.GeoJsonTooltip(fields=['name'], aliases=['Water feature'])).add_to(view)

    well_features = []
    unmatched = 'Unknown within 500 m' if coverage_incomplete else 'No feature within 500 m'
    # Draw observed matches over the gray wells when points overlap at province scale.
    for row in sorted(wells, key=lambda well: well['observed_distance_m'] is not None):
        distance = row['observed_distance_m']
        well_features.append({'type': 'Feature', 'id': row['source_row'], 'geometry': row['geometry'],
                              'properties': {
                                  'licence': popup_text(row['well_licence_number']),
                                  'distance': f'{distance:,.2f} m' if distance is not None else unmatched,
                                  'feature': feature_labels.get(row['nearest_source_feature_id'], '—'),
                                  'color': WELL_COLORS[classify_distance(distance)['color']],
                              }})
    markers = folium.GeoJson({'type': 'FeatureCollection', 'features': well_features},
                             marker=folium.CircleMarker(radius=7 if focus else 3, stroke=False, fill=True, fill_opacity=0.78),
                             style_function=lambda feature: {'fillColor': feature['properties']['color']},
                             popup=folium.GeoJsonPopup(fields=['licence', 'distance', 'feature'],
                                                       aliases=['ST37 licence', 'Observed result', 'Water feature']))
    markers.add_to(view)
    view.fit_bounds(cast(list[list[float]], markers.get_bounds()), padding=(20, 20), max_zoom=15 if focus else 12)
    return view
