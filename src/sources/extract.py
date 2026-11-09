"""Prepare immutable regional GIS packages directly from local publisher downloads."""
import hashlib
import json
import os
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from pathlib import Path

import pyogrio
from pyproj import Transformer

from src.artifacts import write_json
from src.config import Source, StudyArea
from src.sources.common import query_bounds, verify_crs
from src.sources.files import spatial_path

FORMAT = 'alberta-regional-extract'
DATA_MEMBER = 'extract.gpkg'
MANIFEST_MEMBER = 'extract_manifest.json'
MAX_MANIFEST_BYTES = 4*1024**2


def _digest(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle,'sha256').hexdigest()


def parent_fingerprint(path: Path):
    """Stream the original bytes without creating another province-wide copy."""
    path=path.resolve()
    if path.is_file():
        files=[path];kind='file'
    elif path.is_dir() and path.suffix.lower()=='.gdb':
        entries=list(path.rglob('*'))
        if any(p.is_symlink() for p in entries):
            raise ValueError('FileGDB input must not contain symbolic links')
        files=sorted(p for p in entries if p.is_file());kind='filegdb_directory'
    else:
        raise ValueError('Provide an existing local GIS file/ZIP or a .gdb directory')
    if not 1<=len(files)<=10000:
        raise ValueError('Original GIS input has an unsupported file count')
    inventory=[]
    for item in files:
        before=item.stat();checksum=_digest(item);after=item.stat()
        if (before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_size,after.st_mtime_ns,after.st_ctime_ns):
            raise ValueError('Original input changed during hashing; close writers and retry')
        inventory.append({'name':item.name if kind=='file' else item.relative_to(path).as_posix(),
                          'size_bytes':after.st_size,'sha256':checksum})
    fingerprint=(inventory[0]['sha256'] if kind=='file' else
                 hashlib.sha256(json.dumps(inventory,sort_keys=True,separators=(',',':')).encode()).hexdigest())
    return {'path':str(path),'kind':kind,'sha256':fingerprint,
            'size_bytes':sum(x['size_bytes'] for x in inventory),'file_count':len(inventory)}


def inspect_original(source: Source):
    if source.kind!='file' or source.role!='analysis' or source.local_path is None or source.csv_x_field:
        raise ValueError('Regional preparation requires a local spatial file/ZIP or .gdb, not a coordinate CSV/API')
    path=source.local_path.resolve()
    if path.is_dir():
        if path.suffix.lower()!='.gdb':
            raise ValueError('Directory input must be a FileGDB (.gdb)')
        if any(p.is_symlink() for p in path.rglob('*')):
            raise ValueError('FileGDB input must not contain symbolic links')
        dataset=str(path)
    elif path.is_file():
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                if MANIFEST_MEMBER in archive.namelist():
                    raise ValueError('Input is already a regional extract; use the original publisher input for preparation')
        else:
            if path.suffix.lower() not in ('.gpkg','.geojson','.json'):
                raise ValueError('Use a single GeoPackage/GeoJSON, a .gdb directory, or ZIP multi-file GIS inputs first')
            if path.suffix.lower()=='.gpkg' and any(Path(str(path)+suffix).exists() for suffix in ('-wal','-journal')):
                raise ValueError('Close/checkpoint GeoPackage writers and remove active sidecars before preparation')
        # This local preparation route reads members in place; it never expands
        # the whole ZIP to disk. Normal acquisition keeps its existing limits.
        dataset=spatial_path(path,source.archive_member,max_uncompressed_bytes=None)
    else:
        raise ValueError('Original GIS input is missing')
    layers=[{'name':str(row[0]),'geometry_type':str(row[1])} for row in pyogrio.list_layers(dataset)]
    names=[row['name'] for row in layers]
    layer=source.file_layer or (names[0] if len(names)==1 else None)
    if source.file_layer and source.file_layer not in names:
        raise ValueError('Configured layer is absent from the original input')
    info=pyogrio.read_info(dataset,layer=layer,force_feature_count=False,force_total_bounds=False) if layer else None
    metadata=None if info is None else {k:info[k].tolist() if hasattr(info[k],'tolist') else info[k]
        for k in ['driver','crs','geometry_type','features','fields','dtypes','total_bounds']}
    return dataset,layer,{'available_layers':layers,'selected_layer':layer,'metadata':metadata}


def extract_lineage(path: Path, source: Source, area: StudyArea):
    """Enforce the prepared scope before a regional file can imply coverage."""
    if not zipfile.is_zipfile(path):
        return None
    with zipfile.ZipFile(path) as archive:
        matches=[m for m in archive.infolist() if m.filename==MANIFEST_MEMBER]
        if not matches:
            return None
        if len(matches)!=1 or matches[0].file_size>MAX_MANIFEST_BYTES:
            raise ValueError('Regional extract manifest is ambiguous or too large')
        manifest=json.loads(archive.read(matches[0]))
        if manifest.get('format')!=FORMAT or manifest.get('version')!=1:
            raise ValueError('Regional extract manifest format/version is unsupported')
        if manifest.get('study_area')!=area.model_dump(mode='json'):
            raise ValueError('Regional extract was prepared for a different study area; prepare another extract')
        if (manifest.get('source_key')!=source.key or manifest.get('category')!=source.category or
                manifest.get('field_mapping')!=source.field_mapping):
            raise ValueError('Regional extract source/category/field mapping differs from configuration')
        if manifest.get('environmental_margin_m')!=(500 if source.category else 0):
            raise ValueError('Regional extract has an inconsistent environmental margin')
        verify_crs(manifest.get('native_crs'),source)
        members=[m for m in archive.infolist() if m.filename==DATA_MEMBER]
        if len(members)!=1:
            raise ValueError('Regional extract must contain exactly one expected GeoPackage')
        with archive.open(members[0]) as handle:
            if hashlib.file_digest(handle,'sha256').hexdigest()!=manifest.get('data_sha256'):
                raise ValueError('Regional extract data checksum mismatch')
        return manifest


def _existing(folder,source,area,identity):
    report=json.loads((folder/'report.json').read_text())
    path=folder/'extract.zip'
    if report.get('artifact_id')!=identity or _digest(path)!=report.get('package_sha256'):
        raise ValueError('Existing immutable regional extract is corrupt')
    if extract_lineage(path,source,area)!=report['manifest']:
        raise ValueError('Regional extract report does not match its embedded provenance')
    expected={**report['catalogue_entry'],'local_path':'extract.zip'}
    if json.loads((folder/'source.json').read_text())!={'sources':[expected]}:
        raise ValueError('Regional extract catalogue fragment is corrupt')
    return {**report,'package_path':str(path)}


def prepare_extract(source: Source, area: StudyArea, output_root: Path, *,
                    max_records=10000,max_output_bytes=512*1024**2,progress=lambda _:None):
    if area.mode!='live':
        raise ValueError('Prepare regional inputs for a live study-area configuration')
    if not 1<=max_records<=100000 or not 1024<=max_output_bytes<=512*1024**2:
        raise ValueError('Extract limits must be 1–100,000 records and 1 KiB–512 MiB')
    if not (source.publisher and source.downloaded_at and (source.url or source.metadata_url) and source.license_note):
        raise ValueError('Record publisher, download date, publisher URL and terms before preparation')
    identifier='source_feature_id' if source.category else 'source_well_id'
    if identifier not in source.field_mapping:
        raise ValueError('Regional preparation requires an explicit identifier field mapping')
    progress('Inspecting original GIS layer')
    dataset,layer,inspection=inspect_original(source)
    if layer is None:
        raise ValueError('Original input has multiple layers; inspect and configure file_layer')
    metadata=inspection['metadata'];crs=verify_crs(metadata['crs'],source)
    fields=sorted(set(source.field_mapping.values()))
    if not set(fields)<=set(metadata['fields']):
        raise ValueError('Configured fields are absent from the original layer')
    progress('Hashing original input without copying it')
    parent=parent_fingerprint(source.local_path)
    request={'version':1,'source':source.model_dump(mode='json'),'parent_input':parent,
             'study_area':area.model_dump(mode='json'),'max_records':max_records,'max_output_bytes':max_output_bytes,
             'gdal_version':pyogrio.__gdal_version_string__,'pyogrio_version':pyogrio.__version__}
    identity=hashlib.sha256(json.dumps(request,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    output_root=output_root.resolve();output_root.mkdir(parents=True,exist_ok=True);folder=output_root/identity
    if folder.exists():
        progress('Verifying and reusing the existing regional package')
        report=_existing(folder,source,area,identity)
        if parent_fingerprint(source.local_path)!=parent:
            raise ValueError('Original input changed during preparation')
        return report
    environmental=source.category is not None
    bounds=Transformer.from_crs(3400,crs,always_xy=True).transform_bounds(
        *query_bounds(area,environmental=environmental),densify_pts=21)
    progress('Reading the study-area subset with a record cap')
    frame=pyogrio.read_dataframe(dataset,layer=layer,bbox=bounds,columns=fields,max_features=max_records+1)
    verify_crs(frame.crs,source)
    if len(frame)>max_records:
        raise ValueError('Regional extract exceeds the record cap; select a smaller study area (no truncation)')
    # Retain native geometries, including invalid/duplicate records returned by
    # the provider, so the normal pipeline still performs contract quarantine.
    frame=frame.sort_values(source.field_mapping[identifier],kind='stable',key=lambda values:values.astype(str))
    with tempfile.TemporaryDirectory(prefix='.preparing-',dir=output_root) as temporary:
        progress('Writing the bounded regional package')
        work=Path(temporary);data=work/DATA_MEMBER
        frame.to_file(data,driver='GPKG',layer='extract',engine='pyogrio',index=False)
        if data.stat().st_size>max_output_bytes:
            raise ValueError('Regional GeoPackage exceeds the output byte cap; choose a smaller area')
        # GPKG's automatic wall-clock metadata is not input identity.
        with closing(sqlite3.connect(data)) as conn:
            with conn:
                conn.execute("UPDATE gpkg_contents SET last_change='1980-01-01T00:00:00.000Z'")
            # A fresh SQLite backup also normalizes header change counters;
            # provider timing must not create different input bytes on a rerun.
            with closing(sqlite3.connect(work/'normalized.gpkg')) as normalized:
                conn.backup(normalized)
        os.replace(work/'normalized.gpkg',data)
        if data.stat().st_size>max_output_bytes:
            raise ValueError('Regional GeoPackage exceeds the output byte cap; choose a smaller area')
        manifest={'format':FORMAT,'version':1,'source_key':source.key,'category':source.category,
                  'field_mapping':source.field_mapping,'original_source':source.model_dump(mode='json'),
                  'parent_input':parent,'study_area':area.model_dump(mode='json'),
                  'environmental_margin_m':500 if environmental else 0,'native_crs':crs.to_string(),
                  'native_query_bounds':list(bounds),'original_layer':layer,'selected_fields':fields,
                  'record_count':len(frame),'data_sha256':_digest(data),
                  'selection_note':'Provider bbox candidates, native geometry retained; normal ingestion validates/clips. Preparation does not verify publisher coverage.',
                  'gdal_version':request['gdal_version'],'pyogrio_version':request['pyogrio_version']}
        manifest_bytes=json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()
        if len(manifest_bytes)>MAX_MANIFEST_BYTES:
            raise ValueError('Regional extract manifest exceeds its byte cap')
        package=work/'extract.zip'
        with zipfile.ZipFile(package,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
            for name,payload in [(DATA_MEMBER,None),(MANIFEST_MEMBER,manifest_bytes)]:
                entry=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED
                if payload is None:
                    with data.open('rb') as incoming,archive.open(entry,'w') as target:
                        while chunk:=incoming.read(1024*1024):target.write(chunk)
                else:archive.writestr(entry,payload)
        if package.stat().st_size>max_output_bytes:
            raise ValueError('Regional package exceeds the output byte cap; choose a smaller area')
        progress('Checking the original checksum again before publishing')
        if parent_fingerprint(source.local_path)!=parent:
            raise ValueError('Original input changed during preparation; no extract was published')
        prepared={**source.model_dump(mode='json'),'local_path':'extract.zip',
                  'file_layer':'extract','archive_member':DATA_MEMBER,'native_crs':crs.to_string()}
        report={'artifact_id':identity,'record_count':len(frame),'package_bytes':package.stat().st_size,
                'package_sha256':_digest(package),'manifest':manifest,'catalogue_entry':prepared}
        write_json(work/'report.json',report);write_json(work/'source.json',{'sources':[prepared]})
        data.unlink()  # Only the bounded zipped GPKG and metadata are retained.
        try:os.rename(work,folder)
        except OSError:
            if not folder.exists():raise
            return _existing(folder,source,area,identity)
    return {**report,'package_path':str(folder/'extract.zip')}
