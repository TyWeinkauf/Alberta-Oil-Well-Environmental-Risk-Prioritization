"""Region configuration and deterministic sampling of retained ST37 rows."""
import csv
import hashlib
import json
import math
from pathlib import Path

import yaml
from pydantic import Field, model_validator
from pyproj import CRS, Transformer
from shapely.geometry import box

from src.config import ROOT, StrictModel
from src.sources.st37 import CSV_FIELDS, FIELDS, checksum, row_errors

REGION_IDS = ('red_deer', 'drayton_valley')
SELECTION_METHOD = 'smallest SHA-256 of UTF-8 seed:region:licence'


class Region(StrictModel):
    name: str = Field(min_length=1)
    bbox_wgs84: tuple[float, float, float, float]

    @model_validator(mode='after')
    def valid_bounds(self):
        west, south, east, north = self.bbox_wgs84
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError('Expected a valid [west, south, east, north] WGS84 extent')
        return self


class DemoRegions(StrictModel):
    sample_limit: int = Field(ge=1, le=100)
    sample_seed: int
    regions: dict[str, Region]

    @model_validator(mode='after')
    def distinct_regions(self):
        if set(self.regions) != set(REGION_IDS):
            raise ValueError('Define both red_deer and drayton_valley')
        first, second = (box(*self.regions[key].bbox_wgs84) for key in REGION_IDS)
        if first.intersects(second):
            raise ValueError('Classroom regions must have disjoint boundaries')
        return self


def load_regions(path: Path = ROOT / 'config/demo_regions.yml') -> DemoRegions:
    return DemoRegions.model_validate(yaml.safe_load(path.read_text(encoding='utf-8')))


def coordinate_reference(identifier: str | None, evidence: str | None) -> dict | None:
    if identifier is None and evidence is None:
        return None
    if not identifier or not evidence or not evidence.strip():
        raise ValueError('Provide both the Excel coordinate CRS and its source evidence')
    crs = CRS.from_user_input(identifier)
    if not crs.is_geographic or crs.to_epsg() is None or len(crs.axis_info) != 2 or any(
        axis.unit_name != 'degree' for axis in crs.axis_info
    ):
        raise ValueError('ST37 longitude/latitude require a geographic EPSG CRS in degrees')
    return {'crs': f'EPSG:{crs.to_epsg()}', 'evidence': evidence.strip()}


def project_from(source_crs: str | int, target_crs: str | int) -> Transformer:
    return Transformer.from_crs(source_crs, target_crs, always_xy=True, allow_ballpark=False)


def sample_inventory(path: Path, source_hash: str, source_rows: int, accepted_rows: int,
                     config: DemoRegions, coordinate: dict | None) -> dict:
    """Select candidates by region before ranking by original textual licence ID."""
    if checksum(path) != source_hash:
        raise ValueError('Retained inventory checksum differs from its ST37 preparation report')
    candidates: dict[str, dict] = {key: {} for key in REGION_IDS}
    to_display = project_from(coordinate['crs'], 4326) if coordinate else None
    count = accepted = 0
    with path.open(encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != CSV_FIELDS:
            raise ValueError('Unexpected retained ST37 inventory columns')
        for row in reader:
            count += 1
            if count > source_rows or None in row or None in row.values():
                raise ValueError('Unexpected row in retained ST37 inventory')
            errors = json.loads(row['validation_errors']) if row['validation_errors'] != '[]' else []
            if not isinstance(errors, list):
                raise ValueError('Invalid rejection data in retained ST37 inventory')
            if errors:
                continue
            accepted += 1
            longitude, latitude = float(row['SH_Actual_Longitude']), float(row['SH_Actual_Latitude'])
            if to_display:
                longitude, latitude = to_display.transform(longitude, latitude, errcheck=True)
            if not (math.isfinite(longitude) and math.isfinite(latitude)):
                raise ValueError('Invalid coordinates in retained ST37 inventory')
            for key, region in config.regions.items():
                west, south, east, north = region.bbox_wgs84
                if west <= longitude <= east and south <= latitude <= north:
                    well = {field: row[field] for field in FIELDS}
                    licence = well['Well_Licence_Number']
                    if licence in candidates[key] or row_errors(well):
                        raise ValueError('Invalid or duplicate licence in regional ST37 candidates')
                    candidates[key][licence] = {
                        'source_row': int(row['source_row']), 'raw': well,
                        'quality_warnings': row['quality_warnings'],
                    }
    if count != source_rows or accepted != accepted_rows or checksum(path) != source_hash:
        raise ValueError('Inventory row count or checksum changed during preparation')
    output = {}
    for key in REGION_IDS:
        regional = candidates[key]
        ranked = sorted(regional, key=lambda licence: (
            hashlib.sha256(f'{config.sample_seed}:{key}:{licence}'.encode()).digest(), licence))
        selected = sorted(ranked[:config.sample_limit])
        if not selected:
            raise ValueError(f'No retained ST37 wells in {config.regions[key].name}')
        output[key] = {
            'candidate_count': len(regional),
            'wells': [regional[licence] for licence in selected],
        }
    return output
