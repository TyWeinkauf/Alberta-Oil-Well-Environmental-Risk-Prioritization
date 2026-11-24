"""Transactional, repeatable staging of prepared ST37 rows, including rejects."""
import csv
import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from psycopg.types.json import Jsonb
from pyproj import CRS
from sqlalchemy import Connection, Engine, text

from src.config import ROOT, load_study_area
from src.db.migrations import migrate
from src.db.workflow import serialized_workflow
from src.sources.st37 import FIELDS, finite_number, parse_date, read_prepared_st37, retained_st37_report, verify_prepared

ST37_LICENSE_NOTE = 'AER ST37 surface-hole workbook for educational noncommercial use. AER source attribution retained.'
ST37_INVENTORY_PAGE_SIZE = 100


def st37_import_snapshots(conn: Connection) -> list[dict]:
    """Return available inventory headers without initializing a fresh database."""
    if conn.execute(text("SELECT to_regclass('screening.st37_imports')")).scalar_one() is None:
        return []
    return [dict(row) for row in conn.execute(text('''SELECT import_id, imported_at,
        record_count, accepted_count, quarantined_count, coordinate_crs, crs_evidence, release_date,
        source_metadata->'source'->>'worksheet' AS worksheet
        FROM screening.st37_imports ORDER BY imported_at DESC, import_id DESC''')).mappings()]


def st37_inventory_page(engine: Engine, import_id: UUID, *, offset: int = 0, licence: str = '') -> list[dict]:
    """Read at most one page of original worksheet values from the selected snapshot."""
    licence_filter = 'AND well_licence_number=:licence' if licence else ''
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(text(f'''SELECT source_row, raw_payload,
            validation_errors, quality_warnings FROM screening.st37_surface_holes
            WHERE import_id=:id {licence_filter}
            ORDER BY source_row LIMIT :limit OFFSET :offset'''),
            {'id': import_id, 'licence': licence, 'limit': ST37_INVENTORY_PAGE_SIZE,
             'offset': offset}).mappings()]


def safe_date(value):
    try:
        return parse_date(value)
    except ValueError:
        return None


def documented_st37_crs(coordinate_crs, crs_evidence):
    if bool(coordinate_crs) != bool(crs_evidence and crs_evidence.strip()):
        raise ValueError('Coordinate CRS and publisher datum evidence must be supplied together')
    if not coordinate_crs:
        return None
    crs = CRS.from_user_input(coordinate_crs)
    srid = crs.to_epsg()
    if not crs.is_geographic or not srid:
        raise ValueError('ST37 latitude/longitude requires a documented geographic EPSG CRS')
    return f'EPSG:{srid}'


@serialized_workflow
def import_st37_workbook(engine, workbook: Path, raw_root: Path, *,
                         coordinate_crs=None, crs_evidence=None, release_date=None,
                         progress=lambda _: None):
    """Prepare or reuse the retained workbook and stage its complete inventory."""
    coordinate_crs = documented_st37_crs(coordinate_crs, crs_evidence)
    area = load_study_area(ROOT / 'config/study_area.live.yml')
    report = retained_st37_report(workbook, area, raw_root, progress=progress)
    progress('Staging the complete ST37 inventory in PostGIS')
    return import_st37(engine, report, license_note=ST37_LICENSE_NOTE,
                       coordinate_crs=coordinate_crs, crs_evidence=crs_evidence,
                       release_date=release_date)


@serialized_workflow
def import_st37(engine, report_path, *, license_note, coordinate_crs=None,
                crs_evidence=None, downloaded_at=None, release_date=None):
    """Keep all rows, and never publish screening results from a wells-only import.

    With no coordinate CRS the inventory retains coordinates but geom stays NULL.
    A declared geographic EPSG CRS and evidence are required to create geometry.
    """
    if not license_note or not license_note.strip():
        raise ValueError('Record the permitted use and AER attribution before importing')
    coordinate_crs = documented_st37_crs(coordinate_crs, crs_evidence)
    srid = int(coordinate_crs.split(':')[1]) if coordinate_crs else None
    if downloaded_at:
        downloaded_at = datetime.fromisoformat(downloaded_at)
        if downloaded_at.utcoffset() is None:
            raise ValueError('Download timestamp requires a timezone offset')
    if release_date:
        release_date = date.fromisoformat(release_date)
    report = read_prepared_st37(report_path)
    verify_prepared(report)
    declaration = {'identity': report['identity'], 'inventory_checksum': report['artifacts']['inventory']['sha256'],
                   'license_note': license_note, 'coordinate_crs': coordinate_crs, 'crs_evidence': crs_evidence,
                   'downloaded_at': str(downloaded_at) if downloaded_at else None,
                   'release_date': str(release_date) if release_date else None}
    identity = hashlib.sha256(json.dumps(declaration, sort_keys=True).encode()).hexdigest()
    import_id = str(uuid5(NAMESPACE_URL, f'alberta-st37:{identity}'))
    migrate(engine)
    with engine.begin() as conn:
        prior = conn.execute(text('SELECT import_id FROM screening.st37_imports WHERE import_id=:id'),
                             {'id': import_id}).scalar_one_or_none()
        if prior is None:
            conn.execute(text('''INSERT INTO screening.st37_imports
                (import_id,content_identity,source_checksum,inventory_checksum,source_metadata,
                 coordinate_crs,crs_evidence,license_note,downloaded_at,release_date,
                 record_count,accepted_count,quarantined_count)
                VALUES (:id,:identity,:sha,:inventory,CAST(:metadata AS jsonb),:crs,:evidence,:license,
                        :downloaded,:release,:records,:accepted,:quarantined)'''),
                {'id': import_id, 'identity': report['identity'], 'sha': report['source']['sha256'],
                 'inventory': declaration['inventory_checksum'], 'metadata': json.dumps(report),
                 'crs': coordinate_crs, 'evidence': crs_evidence, 'license': license_note,
                 'downloaded': downloaded_at, 'release': release_date,
                 'records': report['source_rows'], 'accepted': report['accepted_rows'],
                 'quarantined': report['quarantined_rows']})
            columns = '''import_id,source_row,well_licence_number,licensee_name,licence_status,
                licence_status_date,ground_elevation,spud_date,most_recent_final_drill_date,
                energy_development_category,legal_location,surface_latitude,surface_longitude,
                validation_errors,quality_warnings,raw_payload'''
            with Path(report['artifacts']['inventory']['path']).open(encoding='utf-8', newline='') as handle, \
                 conn.connection.driver_connection.cursor() as cursor, \
                 cursor.copy(f'COPY screening.st37_surface_holes ({columns}) FROM STDIN') as copy:
                for row in csv.DictReader(handle):
                    raw = {field: row[field] for field in FIELDS}
                    copy.write_row((import_id, int(row['source_row']), raw['Well_Licence_Number'],
                        raw['Licensee'] or None, raw['Licence_Status'] or None,
                        safe_date(raw['Licence_Status_Date']), finite_number(raw['Ground_Elevation']),
                        safe_date(raw['Spud_Date']), safe_date(raw['Most_Recent_Final_Drill_Date']),
                        raw['Energy_Devlpmt_Category_Type'] or None, raw['Licence_Surface_Location_Label'] or None,
                        finite_number(raw['SH_Actual_Latitude']), finite_number(raw['SH_Actual_Longitude']),
                        Jsonb(json.loads(row['validation_errors'])), Jsonb(json.loads(row['quality_warnings'])), Jsonb(raw)))
            # Check bytes again before publication, including changes during COPY.
            verify_prepared(report)
            if srid:
                conn.execute(text('''UPDATE screening.st37_surface_holes
                    SET geom=ST_Transform(ST_SetSRID(ST_MakePoint(surface_longitude,surface_latitude),:srid),3400)
                    WHERE import_id=:id AND validation_errors='[]'::jsonb'''), {'id': import_id, 'srid': srid})
        counts = dict(conn.execute(text('''SELECT count(*) AS records,
            count(*) FILTER (WHERE validation_errors='[]'::jsonb) AS accepted,
            count(*) FILTER (WHERE validation_errors<>'[]'::jsonb) AS quarantined,
            count(geom) AS geometries,
            count(*) FILTER (WHERE geom IS NOT NULL AND (ST_SRID(geom)<>3400 OR NOT ST_IsValid(geom))) AS invalid_geometries
            FROM screening.st37_surface_holes WHERE import_id=:id'''), {'id': import_id}).mappings().one())
        if (counts['records'], counts['accepted'], counts['quarantined']) != (
                report['source_rows'], report['accepted_rows'], report['quarantined_rows']):
            raise ValueError('ST37 database counts do not reconcile with the prepared source')
        if counts['geometries'] != (report['accepted_rows'] if srid else 0) or counts['invalid_geometries']:
            raise ValueError('ST37 geometry verification failed')
    return {'import_id': import_id, 'reused': prior is not None, **counts,
            'coordinate_crs': coordinate_crs, 'screening_run_published': False}
