"""Synthetic water service: two different layers deliberately share an OBJECTID."""
import json
import re
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from src.config import Source, SourceCatalog


@contextmanager
def hydro_service():
    state = {'requests': 0, 'missing_page': False, 'invalid_geometry': False, 'revision': 'original', 'queries': []}
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            state['requests'] += 1
            path = urlsplit(self.path).path
            query = parse_qs(urlsplit(self.path).query)
            if not path.endswith('/query'):
                response = {'supportedQueryFormats': 'JSON, geoJSON', 'maxRecordCount': 200,
                    'sourceSpatialReference': {'latestWkid': 3400}, 'fields': [
                        {'name': 'OBJECTID', 'type': 'esriFieldTypeOID'},
                        {'name': 'NAME', 'type': 'esriFieldTypeString'},
                        {'name': 'FEATURE_TYPE', 'type': 'esriFieldTypeString'},
                        {'name': 'SOURCE', 'type': 'esriFieldTypeString'}]}
            else:
                state['queries'].append(query)
                layer = int(path.split('/')[-2])
                feature_type = 'LAKE-PER' if layer == 0 else 'STR-PER'
                geometry = {'type': 'Polygon', 'coordinates': [[[-115.001,53.249],[-114.999,53.249],[-114.999,53.251],[-115.001,53.251],[-115.001,53.249]]]}
                if layer == 1:
                    geometry = {'type': 'LineString', 'coordinates': [[-115.0,53.25],[-115.0,53.26]]}
                features = [] if layer == 2 else [{'type': 'Feature', 'properties': {
                    'OBJECTID': 7, 'NAME': state['revision'], 'FEATURE_TYPE': feature_type, 'SOURCE': 'Synthetic raw attribute'},
                    'geometry': geometry if not (state['invalid_geometry'] and layer == 1) else None}]
                allowed = re.findall("'([^']+)'", query.get('where', [''])[0])
                if allowed:
                    features = [feature for feature in features if feature['properties']['FEATURE_TYPE'] in allowed]
                if query.get('returnCountOnly') == ['true']:
                    response = {'count': len(features)}
                elif query.get('returnIdsOnly') == ['true']:
                    response = {'objectIds': [7] if features else None}
                else:
                    if state['missing_page'] and layer == 1:
                        features = []
                    response = {'type': 'FeatureCollection', 'features': features}
            encoded = json.dumps(response).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(encoded)
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}/MapServer'
    sources = [Source(key=f'synthetic_water_{layer}', kind='arcgis', role='analysis', category='water',
        priority='optional' if layer == 2 else 'core', enabled=layer != 2, verified=True,
        url=base, native_crs='EPSG:3400', layer_id=layer, license_note='Synthetic test permission',
        field_mapping={'source_feature_id': 'OBJECTID', 'name': 'NAME', 'feature_type_code': 'FEATURE_TYPE'},
        arcgis_where="FEATURE_TYPE IN ('LAKE-PER','STR-PER')", arcgis_preserve_properties=True,
        coverage_note='Synthetic complete coverage of configured pilot plus 500 m') for layer in range(3)]
    try:
        yield SourceCatalog(sources=sources), state
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
