"""ArcGIS service inspection and ID-batched acquisition with complete-page checks."""
import json

from src.config import Source, StudyArea
from src.sources.common import Acquisition, mapped_record, query_bounds, verify_crs
from src.sources.http import HttpCache
from pyproj import CRS


def _json(snapshot):
    value=snapshot.json()
    if not isinstance(value,dict) or 'error' in value:
        raise ValueError('ArcGIS returned an error or malformed response; source is not complete')
    return value


def acquire_arcgis(source: Source, area: StudyArea, cache: HttpCache, *, refresh: bool=False,
                   max_records: int=10000) -> Acquisition:
    if not source.url or source.layer_id is None:
        raise ValueError(f'{source.key}: verified service URL/layer ID required')
    base=str(source.url).rstrip('/')
    if not base.endswith(('/MapServer','/FeatureServer')):
        raise ValueError('ArcGIS URL must name a MapServer/FeatureServer; configure layer_id separately')
    layer=f'{base}/{source.layer_id}'
    raw=[cache.get(layer,{'f':'json'},refresh=refresh)]
    metadata=_json(raw[0])
    formats=metadata.get('supportedQueryFormats','')
    if 'geojson' not in formats.lower():
        raise ValueError(f'{source.key}: service must explicitly support GeoJSON queries')
    field_info=metadata.get('fields',[])
    fields={field['name'] for field in field_info}
    if not set(source.field_mapping.values())<=fields:
        raise ValueError(f'{source.key}: configured mapping does not match acquired ArcGIS fields')
    oid=metadata.get('objectIdField') or next((f['name'] for f in field_info if f.get('type')=='esriFieldTypeOID'),None)
    if not oid:
        raise ValueError('ArcGIS object ID field is required for complete paging')
    spatial_reference=(metadata.get('extent') or {}).get('spatialReference') or metadata.get('sourceSpatialReference') or {}
    wkid=spatial_reference.get('latestWkid') or spatial_reference.get('wkid')
    actual_crs=spatial_reference.get('wkt') or (f'EPSG:{wkid}' if wkid else None)
    native_crs=verify_crs(actual_crs,source).to_string()
    environmental=source.category is not None
    left,bottom,right,top=query_bounds(area,environmental=environmental)
    common={'where':source.arcgis_where,'geometryType':'esriGeometryEnvelope','inSR':3400,
            'geometry':json.dumps({'xmin':left,'ymin':bottom,'xmax':right,'ymax':top,'spatialReference':{'wkid':3400}},separators=(',',':')),
            'spatialRel':'esriSpatialRelIntersects'}
    raw.append(cache.get(layer+'/query',{**common,'f':'json','returnCountOnly':'true'},refresh=refresh))
    expected=_json(raw[-1]).get('count')
    if not isinstance(expected,int) or isinstance(expected,bool) or not 0<=expected<=max_records:
        raise ValueError('ArcGIS count missing/invalid or study area exceeds record limit; choose a smaller area')
    raw.append(cache.get(layer+'/query',{**common,'f':'json','returnIdsOnly':'true'},refresh=refresh))
    id_response=_json(raw[-1]);ids=id_response.get('objectIds')
    if ids is None and expected==0 and 'objectIds' in id_response:
        ids=[]
    if not isinstance(ids,list) or id_response.get('exceededTransferLimit') or len(ids)!=expected:
        raise ValueError('ArcGIS object ID response is incomplete or changed during acquisition')
    if any(not isinstance(i,int) or isinstance(i,bool) for i in ids) or len(set(ids))!=len(ids):
        raise ValueError('ArcGIS object ID response contains duplicate or invalid IDs')
    batch_size=min(int(metadata.get('maxRecordCount',1000)),source.arcgis_batch_size)
    if batch_size<1:
        raise ValueError('ArcGIS maximum record count is invalid')
    records=[]
    for offset in range(0,len(ids),batch_size):
        batch=sorted(ids)[offset:offset+batch_size]
        params={'f':'geojson','where':source.arcgis_where,'objectIds':','.join(map(str,batch)),
                'outFields':'*' if source.arcgis_preserve_properties else ','.join(sorted(set(source.field_mapping.values())|{oid})),
                'outSR':4326,'returnGeometry':'true','returnZ':'false','returnM':'false'}
        raw.append(cache.get(layer+'/query',params,refresh=refresh));page=_json(raw[-1])
        declared_crs=(page.get('crs') or {}).get('properties',{}).get('name')
        if declared_crs and not CRS.from_user_input(declared_crs).equals(CRS.from_epsg(4326),ignore_axis_order=True):
            raise ValueError('ArcGIS GeoJSON response CRS conflicts with the requested WGS84 output')
        features=page.get('features')
        if page.get('type')!='FeatureCollection' or not isinstance(features,list) or page.get('exceededTransferLimit'):
            raise ValueError('ArcGIS geometry page is not a complete GeoJSON FeatureCollection')
        observed=[f.get('properties',{}).get(oid) for f in features]
        if len(observed)!=len(batch) or set(observed)!=set(batch):
            raise ValueError('ArcGIS geometry page has missing, duplicate or unexpected records')
        records.extend(mapped_record(source,f['properties'],f.get('geometry'),environmental=environmental)
                       for f in sorted(features,key=lambda f:f['properties'][oid]))
    return Acquisition(source,records,'EPSG:4326',native_crs,raw,
                       {'count':expected,'object_id_field':oid,'fields':sorted(fields),
                        'last_edit_date':(metadata.get('editingInfo') or {}).get('lastEditDate'),
                        'where':source.arcgis_where,'batch_size':batch_size,
                        'query_bounds_3400':[left,bottom,right,top],
                        'environmental_margin_m':500 if environmental else 0})
