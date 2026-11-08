"""Deterministic spatial contracts; rejected rows are explicit, never silent drops."""
from collections import Counter
from dataclasses import dataclass
from typing import Literal

import numpy as np
from pyproj import CRS, Transformer
from pyproj.exceptions import CRSError
from shapely import get_coordinates, transform
from shapely.errors import GEOSException
from shapely.geometry import shape

from src.config import StudyArea

CATEGORIES = {'water', 'protected_area', 'critical_habitat', 'wetland', 'esa'}
WELL_FIELDS = ('licensee_name', 'uwi_if_available', 'operator_name_if_verified', 'lsd_text', 'status')


@dataclass
class ValidationBatch:
    accepted: list[dict]
    rejected: list[dict]


class ContractError(ValueError):
    def __init__(self, code, detail):
        self.code = code
        super().__init__(detail)


def require_crs(value) -> CRS:
    if not value:
        raise ValueError('Source CRS is required; it must not be guessed')
    try:
        crs = CRS.from_user_input(value)
    except (CRSError, TypeError) as exc:
        raise ValueError('Unknown source CRS') from exc
    if not (crs.is_geographic or crs.is_projected):
        raise ValueError('Source CRS must be geographic or projected')
    return crs


def validate_records(rows: list, entity: Literal['wells', 'features'], crs_value,
                     study_area: StudyArea) -> ValidationBatch:
    """Validate IDs, geometry, CRS, extent and fields; project accepted rows to 3400.

    All occurrences of a duplicate ID are quarantined, so row ordering cannot
    arbitrarily choose which conflicting source record becomes authoritative.
    """
    if entity not in ('wells', 'features') or not isinstance(rows, list):
        raise ValueError('Expected wells/features as a list of source records')
    crs = require_crs(crs_value)
    to_wgs84 = Transformer.from_crs(crs, 4326, always_xy=True)
    to_analysis = Transformer.from_crs(crs, study_area.analysis_crs, always_xy=True)
    id_field = 'source_well_id' if entity == 'wells' else 'source_feature_id'
    ids = Counter(row[id_field].strip() for row in rows if isinstance(row, dict)
                  and isinstance(row.get(id_field), str) and row[id_field].strip())
    accepted, rejected = [], []
    for index, row in enumerate(rows):
        reference = f'{entity}/{index}'
        try:
            if not isinstance(row, dict):
                raise ContractError('invalid_record', 'Record must be an object')
            identifier = row.get(id_field)
            if not isinstance(identifier, str) or not identifier.strip():
                raise ContractError('missing_id', f'{id_field} must be a nonempty string')
            identifier = identifier.strip()
            if ids[identifier] > 1:
                raise ContractError('duplicate_id', 'All occurrences of a duplicate identifier are rejected')
            if row.get('geometry') is None:
                raise ContractError('missing_geometry', 'Geometry is required')
            try:
                geometry = shape(row['geometry'])
            except (TypeError, ValueError, AttributeError, KeyError, GEOSException):
                raise ContractError('malformed_geometry', 'Geometry is not valid GeoJSON') from None
            allowed = {'Point'} if entity == 'wells' else {'LineString', 'MultiLineString', 'Polygon', 'MultiPolygon'}
            if geometry.geom_type not in allowed:
                raise ContractError('geometry_type', 'Geometry type is not supported for this entity')
            if geometry.is_empty or not geometry.is_valid or geometry.has_z:
                raise ContractError('invalid_geometry', 'Geometry must be nonempty, valid and two dimensional')
            coordinates = get_coordinates(geometry)
            if not np.isfinite(coordinates).all():
                raise ContractError('invalid_coordinates', 'Coordinates must be finite')
            if crs.is_geographic and (
                (np.abs(coordinates[:, 0]) > 180).any() or (np.abs(coordinates[:, 1]) > 90).any()
            ):
                raise ContractError('invalid_coordinates', 'Geographic coordinates are outside longitude/latitude ranges')
            try:
                geographic = transform(geometry, to_wgs84.transform, interleaved=False)
                projected = transform(geometry, to_analysis.transform, interleaved=False)
            except (ValueError, CRSError):
                raise ContractError('invalid_coordinates', 'Coordinate transformation failed') from None
            if not np.isfinite(get_coordinates(geographic)).all() or not np.isfinite(get_coordinates(projected)).all():
                raise ContractError('invalid_coordinates', 'Coordinate transformation produced nonfinite values')
            west, south, east, north = study_area.bbox_wgs84
            # Features may extend 500 m beyond the extent in future adapters;
            # Phase 1 fixtures must be wholly within the configured demo extent.
            left, bottom, right, top = geographic.bounds
            if not (west <= left <= right <= east and south <= bottom <= top <= north):
                raise ContractError('outside_study_area', 'Geometry is outside the configured study extent')
            fields = WELL_FIELDS if entity == 'wells' else ('name',)
            if any(row.get(field) is not None and not isinstance(row[field], str) for field in fields):
                raise ContractError('invalid_field_type', 'Optional text fields must be strings or null')
            result = {id_field: identifier, 'geometry_wkt': projected.wkt}
            result.update({field: row.get(field) for field in fields})
            if entity == 'wells':
                licensee = row.get('licensee_name')
                result['licensee_search'] = ' '.join(licensee.split()).casefold() if licensee else None
            else:
                if not isinstance(row.get('category'), str) or row['category'] not in CATEGORIES:
                    raise ContractError('invalid_category', 'Environmental category is missing or unsupported')
                result['feature_type'] = row['category']
            accepted.append(result)
        except ContractError as exc:
            rejected.append({'record_reference': reference, 'reason_code': exc.code, 'reason_detail': str(exc)})
    assert len(accepted) + len(rejected) == len(rows)
    return ValidationBatch(accepted, rejected)
