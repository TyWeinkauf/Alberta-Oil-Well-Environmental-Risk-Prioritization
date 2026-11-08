"""Acquisition results retain exact raw responses and a selected-record sidecar."""
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from pyproj import CRS

from src.config import ROOT, Source, StudyArea
from src.spatial.extent import study_geometry
from src.sources.http import Snapshot


def query_bounds(area: StudyArea, *, environmental: bool):
    geometry=study_geometry(area)
    return (geometry.buffer(500) if environmental else geometry).bounds


def mapped_record(source: Source, properties: dict, geometry: dict, *, environmental: bool):
    required='source_feature_id' if environmental else 'source_well_id'
    if required not in source.field_mapping:
        raise ValueError(f'{source.key}: verified mapping for {required} is required')
    missing=set(source.field_mapping.values())-properties.keys()
    if missing:
        raise ValueError(f'{source.key}: mapped source fields are missing: {sorted(missing)}')
    record={name:properties[field] for name,field in source.field_mapping.items()}
    identifier=record.get(required)
    if isinstance(identifier,int) and not isinstance(identifier,bool):
        record[required]=str(identifier)
    record['geometry']=geometry
    if environmental:
        if not source.category:
            raise ValueError(f'{source.key}: environmental category must be configured')
        record['category']=source.category
    return record


@dataclass
class Acquisition:
    source: Source
    records: list[dict]
    records_crs: str
    native_crs: str
    responses: list[Snapshot]
    inspection: dict

    def archive(self,root: Path | None = None) -> tuple[str,Path,dict]:
        root=root or ROOT/'data/raw/live'
        manifest={'source_key':self.source.key,'source_url':str(self.source.url),
                  'native_crs':self.native_crs,'records_crs':self.records_crs,
                  'field_mapping':self.source.field_mapping,'license_note':self.source.license_note,
                  'inspection':self.inspection,
                  'raw_responses':[{**s.metadata,'cached_path':str(s.path)} for s in self.responses],
                  'selected_records':self.records}
        identity={'source':self.source.model_dump(mode='json'),'records_crs':self.records_crs,
                  'native_crs':self.native_crs,'inspection':self.inspection,'selected_records':self.records,
                  'raw_checksums':[s.metadata['checksum_sha256'] for s in self.responses]}
        manifest['content_identity_sha256']=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        payload=json.dumps(manifest,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        checksum=hashlib.sha256(payload).hexdigest()
        destination=root/checksum/'source_bundle.json'
        if destination.exists() and destination.read_bytes()!=payload:
            raise ValueError('Immutable source bundle has been modified')
        if not destination.exists():
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes(payload)
        return checksum,destination,manifest


def verify_crs(actual: str | None,source: Source) -> CRS:
    if not actual:
        raise ValueError(f'{source.key}: acquired dataset has no CRS')
    crs=CRS.from_user_input(actual)
    if not source.native_crs or not crs.equals(CRS.from_user_input(source.native_crs),ignore_axis_order=True):
        raise ValueError(f'{source.key}: acquired CRS does not match verified catalogue metadata')
    return crs
