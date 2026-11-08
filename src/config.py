"""Validated configuration; unverified live sources must remain disabled."""
import hashlib
import json
import os
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

ROOT = Path(__file__).resolve().parents[1]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Source(StrictModel):
    key: str = Field(min_length=1)
    kind: Literal['file', 'arcgis', 'tiles']
    role: Literal['analysis', 'basemap', 'production'] = 'analysis'
    priority: Literal['core', 'optional'] = 'core'
    publisher: str | None = None
    reference_crs: str | None = None
    reference_license: str | None = None
    reference_document: str | None = None
    enabled: bool = False
    url: HttpUrl | None = None
    verified: bool = False
    license_note: str | None = None
    native_crs: str | None = None
    layer_id: int | None = None
    field_mapping: dict[str, str] = Field(default_factory=dict)
    category: Literal['water','protected_area','critical_habitat','wetland','esa'] | None = None
    file_layer: str | None = None
    archive_member: str | None = None
    metadata_url: HttpUrl | None = None
    license_url: HttpUrl | None = None
    coverage_note: str | None = None

    @model_validator(mode='after')
    def require_verified_metadata(self):
        if self.kind == 'tiles' and self.role != 'basemap':
            raise ValueError('Tile sources are basemaps, not analytical distance sources')
        if self.enabled and not (
            self.verified and self.url and self.license_note and self.native_crs
            and (self.role == 'basemap' or self.field_mapping)
            and (self.kind != 'arcgis' or self.layer_id is not None)
        ):
            raise ValueError('An enabled source needs verified URL, permission, CRS, fields and ArcGIS layer ID')
        return self


class SourceCatalog(StrictModel):
    sources: list[Source]

    @model_validator(mode='after')
    def unique_source_keys(self):
        if len({s.key for s in self.sources}) != len(self.sources):
            raise ValueError('Duplicate source key')
        return self


class StudyArea(StrictModel):
    name: str = Field(min_length=1)
    bbox_wgs84: tuple[float, float, float, float]
    analysis_crs: Literal['EPSG:3400']
    thresholds_m: list[float]
    mode: Literal['demo', 'live']

    @model_validator(mode='after')
    def valid_extent_and_thresholds(self):
        west, south, east, north = self.bbox_wgs84
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError('Invalid WGS84 bounding box')
        if not self.thresholds_m or any(not 0 < x <= 10000 for x in self.thresholds_m):
            raise ValueError('Thresholds must be finite and positive (at most 10,000 metres)')
        if self.thresholds_m != sorted(set(self.thresholds_m)):
            raise ValueError('Thresholds must be unique and increasing')
        return self


def load_study_area(path: Path | None = None) -> StudyArea:
    return StudyArea.model_validate(yaml.safe_load((path or ROOT / 'config/study_area.yml').read_text()))


def load_source_catalog(path: Path | None = None) -> SourceCatalog:
    return SourceCatalog.model_validate(yaml.safe_load((path or ROOT / 'config/source_catalog.yml').read_text()))


def config_hash(study_area: StudyArea) -> str:
    payload = json.dumps(study_area.model_dump(), sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def database_url() -> str:
    # An explicitly supplied process binding takes precedence over local .env.
    load_dotenv(ROOT / '.env', override=False)
    value = os.getenv('DATABASE_URL')
    if not value or 'CHANGE_ME' in value:
        raise ValueError('Set DATABASE_URL to a local PostgreSQL/PostGIS database; see README.md')
    return value
