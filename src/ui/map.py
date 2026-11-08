"""Folium markers carry stable primary keys; vendored assets support offline use."""
import base64
import html
from functools import lru_cache

import folium

from src.config import ROOT


def popup_text(value: str) -> str:
    # Folium places popup/tooltip HTML in JavaScript template literals.
    return html.escape(value).replace('`','&#96;').replace('$','&#36;').replace('\\','&#92;')


@lru_cache(maxsize=8)
def asset_uri(relative_path: str, mime: str) -> str:
    return f'data:{mime};base64,'+base64.b64encode((ROOT/relative_path).read_bytes()).decode()


def build_map(records: list[dict], features: list[dict], categories: list[str], *, basemap: bool = False,
              overlays: bool = True) -> folium.Map:
    center = ([sum(r['latitude'] for r in records)/len(records),sum(r['longitude'] for r in records)/len(records)]
              if records else [53.5,-114])
    view = folium.Map(location=center,zoom_start=12,tiles=None,control_scale=True)
    # Do not load third-party CDNs on every render; these same assets work in exported HTML.
    view.default_js = [('leaflet',asset_uri('vendor/leaflet/leaflet.js','text/javascript')),
                       ('jquery',asset_uri('vendor/jquery/jquery.min.js','text/javascript'))]
    view.default_css = [('leaflet_css',asset_uri('vendor/leaflet/leaflet.css','text/css'))]
    if basemap:
        folium.TileLayer('OpenStreetMap').add_to(view)
    if overlays:
        for feature in features:
            if feature['feature_type'] in categories:
                folium.GeoJson(feature['geometry'],name=feature['source_feature_id'],
                    style_function=lambda _: {'color':'#247ba0','weight':2,'fillOpacity':0.12}).add_to(view)
    for row in records:
        identifier = popup_text(row['source_well_id'])
        company = popup_text(row['licensee_name'] or 'Not available from this source')
        # streamlit-folium returns innerText, so attributes/hidden text are lost.
        # A small visible reference survives the bridge without using coordinates.
        token = f'<small>Record reference: {row["well_pk"]}</small><br>'
        popup = f'<section data-well-key="{row["well_pk"]}">{token}<strong>{identifier}</strong><br>{company}<br>View details below the map</section>'
        # Fixed palette from the shared classifier; no untrusted CSS is inserted.
        color = {'red':'#b91c1c','orange':'#c2410c','yellow':'#ca8a04','blue':'#1d4ed8','gray':'#64748b'}[row['color']]
        icon = folium.DivIcon(html=f'<span style="display:block;background:{color};width:18px;height:18px;'
                                  'border:2px solid white;border-radius:50%;box-shadow:0 1px 5px #333"></span>',
                              icon_size=(22,22),icon_anchor=(11,11))
        folium.Marker([row['latitude'],row['longitude']],popup=folium.Popup(popup,max_width=300),
                      tooltip=identifier,title=row['source_well_id'],icon=icon).add_to(view)
    if records:
        view.fit_bounds([[r['latitude'],r['longitude']] for r in records],padding=(35,35),max_zoom=18)
    return view
