"""Transactional, repeatable staging of prepared ST37 rows, including rejects."""
import csv
import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from psycopg.types.json import Jsonb
from pyproj import CRS
from sqlalchemy import text

from src.db.migrations import migrate
from src.db.workflow import serialized_workflow
from src.sources.st37 import FIELDS, finite_number, parse_date, verify_prepared


def safe_date(value):
    try:
        return parse_date(value)
    except ValueError:
        return None


@serialized_workflow
def import_st37(engine, report_path, *, license_note, coordinate_crs=None,
                crs_evidence=None, downloaded_at=None, release_date=None):
    """Keep all rows, and never publish screening results from a wells-only import.

    With no coordinate CRS the inventory retains coordinates but geom stays NULL.
    A declared geographic EPSG CRS and evidence are required to create geometry.
    """
    if not license_note or not license_note.strip():
        raise ValueError('Record the permitted use and AER attribution before importing')
    if bool(coordinate_crs) != bool(crs_evidence and crs_evidence.strip()):
        raise ValueError('Coordinate CRS and publisher datum evidence must be supplied together')
    srid = None
    if coordinate_crs:
        crs = CRS.from_user_input(coordinate_crs)
        srid = crs.to_epsg()
        if not crs.is_geographic or not srid:
            raise ValueError('ST37 latitude/longitude requires a documented geographic EPSG CRS')
        coordinate_crs = f'EPSG:{srid}'
    if downloaded_at:
        downloaded_at = datetime.fromisoformat(downloaded_at)
        if downloaded_at.utcoffset() is None:
            raise ValueError('Download timestamp requires a timezone offset')
    if release_date:
        release_date = date.fromisoformat(release_date)
    report = json.loads(Path(report_path).read_text(encoding='utf-8'))
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
