"""Spatial file/ZIP reader: inspect actual layers/CRS, then read only a bounded subset."""
import zipfile
from pathlib import PurePosixPath

import pandas as pd
import pyogrio
from pyproj import Transformer
from shapely.geometry import mapping

from src.config import Source, StudyArea
from src.sources.common import Acquisition, mapped_record, query_bounds, verify_crs
from src.sources.http import HttpCache


def spatial_path(path,member: str | None=None):
    if not zipfile.is_zipfile(path):
        if member:
            raise ValueError('archive_member configured for a non-ZIP source')
        return str(path)
    with zipfile.ZipFile(path) as archive:
        names=[name.replace('\\','/') for name in archive.namelist()]
        if len(names)>10000 or sum(i.file_size for i in archive.infolist())>2*1024**3:
            raise ValueError('ZIP archive exceeds safe file-count/uncompressed-size limits')
        if any(PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts or ':' in name for name in names):
            raise ValueError('ZIP contains unsafe member paths')
        candidates={name for name in names if name.lower().endswith(('.shp','.gpkg','.geojson'))}
        for name in names:
            parts=PurePosixPath(name).parts
            for index,part in enumerate(parts):
                if part.lower().endswith('.gdb'):
                    candidates.add('/'.join(parts[:index+1]));break
        if member:
            if member not in candidates:
                raise ValueError('Configured archive_member is not an acquired spatial dataset')
        elif len(candidates)!=1:
            raise ValueError('ZIP has ambiguous spatial datasets; inspect it and configure archive_member')
        else:
            member=next(iter(candidates))
    # Braces delimit an archive whose content-addressed filename has no .zip suffix.
    return f'/vsizip/{{{path.resolve()}}}/{member}'


def acquire_file(source: Source,area: StudyArea,cache: HttpCache,*,refresh: bool=False,
                 max_records: int=10000) -> Acquisition:
    if not source.url:
        raise ValueError('Verified spatial download URL is required')
    snapshot=cache.get(str(source.url),refresh=refresh)
    dataset=spatial_path(snapshot.path,source.archive_member)
    layers=pyogrio.list_layers(dataset)
    names=[str(row[0]) for row in layers]
    if source.file_layer:
        if source.file_layer not in names:
            raise ValueError(f'{source.key}: configured layer is absent from downloaded data')
        layer=source.file_layer
    elif len(names)==1:
        layer=names[0]
    else:
        raise ValueError('Spatial download has multiple layers; inspect and configure file_layer')
    info=pyogrio.read_info(dataset,layer=layer)
    crs=verify_crs(info.get('crs'),source)
    if not set(source.field_mapping.values())<=set(info['fields']):
        raise ValueError(f'{source.key}: acquired spatial fields do not match the verified mapping')
    environmental=source.category is not None
    native_bounds=Transformer.from_crs(3400,crs,always_xy=True).transform_bounds(
        *query_bounds(area,environmental=environmental),densify_pts=21)
    frame=pyogrio.read_dataframe(dataset,layer=layer,bbox=native_bounds,
        columns=sorted(set(source.field_mapping.values())),max_features=max_records+1)
    if len(frame)>max_records:
        raise ValueError('Spatial subset exceeds record limit; choose a smaller study area')
    records=[]
    for _,row in frame.iterrows():
        properties={field:(None if pd.isna(row[field]) else row[field].item() if hasattr(row[field],'item') else row[field])
                    for field in source.field_mapping.values()}
        records.append(mapped_record(source,properties,mapping(row.geometry) if row.geometry is not None else None,
                                     environmental=environmental))
    identifier='source_feature_id' if environmental else 'source_well_id'
    records.sort(key=lambda row:str(row.get(identifier,'')))
    return Acquisition(source,records,crs.to_string(),crs.to_string(),[snapshot],
                       {'driver':info['driver'],'layer':layer,'available_layers':names,
                        'fields':list(info['fields']),'geometry_type':info['geometry_type'],
                        'selected_count':len(frame),'native_query_bounds':list(native_bounds),
                        'environmental_margin_m':500 if environmental else 0})
