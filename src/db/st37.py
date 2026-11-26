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
from src.spatial.classification import THRESHOLDS

ST37_LICENSE_NOTE = 'AER ST37 surface-hole workbook for educational noncommercial use. AER source attribution retained.'
ST37_DATUM_EVIDENCE = ROOT / 'docs/evidence/st37_datum_2026-11-23.json'
ST37_INVENTORY_PAGE_SIZE = 100
ST37_INVENTORY_FILTER_FIELDS = ('licence_status', 'energy_development_category')
ST37_INVENTORY_OPTION_LIMIT = 4_000


def st37_import_snapshots(conn: Connection) -> list[dict]:
    """Return available inventory headers without initializing a fresh database."""
    if conn.execute(text("SELECT to_regclass('screening.st37_imports')")).scalar_one() is None:
        return []
    return [dict(row) for row in conn.execute(text('''SELECT import_id, imported_at,
        record_count, accepted_count, quarantined_count, coordinate_crs, crs_evidence, release_date,
        source_metadata->'source'->>'worksheet' AS worksheet
        FROM screening.st37_imports ORDER BY imported_at DESC, import_id DESC''')).mappings()]


def st37_inventory_filter_options(engine: Engine, import_id: UUID, field: str, search: str = '') -> list[str]:
    """Read distinct options with an extra value to detect when a search is needed."""
    if field not in ST37_INVENTORY_FILTER_FIELDS:
        raise ValueError('Unknown ST37 workbook filter')
    search_clause = f"AND strpos(lower(COALESCE({field}, '')), lower(:search)) > 0" if search else ''
    with engine.connect() as conn:
        return list(conn.execute(text(f'''SELECT DISTINCT COALESCE({field}, '') AS option
            FROM screening.st37_surface_holes
            WHERE import_id=:id {search_clause}
            ORDER BY option LIMIT :limit'''),
            {'id': import_id, 'search': search, 'limit': ST37_INVENTORY_OPTION_LIMIT + 1}).scalars())


def st37_well_conditions(filters: dict[str, list[str]] | None, licence: str = '') -> tuple[list[str], dict]:
    """Build bound attribute conditions for an ST37 row aliased as well."""
    conditions = []
    params: dict = {}
    if licence:
        conditions.append('well.well_licence_number=:licence')
        params['licence'] = licence
    for field in ST37_INVENTORY_FILTER_FIELDS:
        values = (filters or {}).get(field)
        if values:
            match = f'well.{field}=ANY(:{field})'
            conditions.append(f'({match} OR well.{field} IS NULL)' if '' in values else match)
            params[field] = values
    return conditions, params


def inventory_selection(import_id: UUID, filters: dict[str, list[str]] | None, licence: str,
                        water_comparison_ids: tuple[UUID, ...]) -> tuple[str, dict]:
    source = 'screening.st37_surface_holes AS well'
    well_conditions, params = st37_well_conditions(filters, licence)
    conditions = ['well.import_id=:id', *well_conditions]
    params['id'] = import_id
    bands = (filters or {}).get('water_band')
    if bands:
        params['water_bands'] = bands
        band = "'unavailable'"
        if water_comparison_ids:
            # Classify the minimum across the same stored comparisons used by the table.
            ranges = ' '.join(f"WHEN min(p.observed_distance_m)<={metres} THEN 'within_{metres}m'"
                              for metres in THRESHOLDS)
            source += f''' LEFT JOIN (
                SELECT p.source_row, CASE {ranges} ELSE 'none_within_500m' END AS band
                FROM screening.st37_waterbody_proximity p
                JOIN screening.waterbody_comparisons c ON c.comparison_id=p.comparison_id
                WHERE c.st37_import_id=:id AND p.comparison_id=ANY(:water_comparisons)
                GROUP BY p.source_row
            ) AS water ON water.source_row=well.source_row'''
            params['water_comparisons'] = list(water_comparison_ids)
            band = "COALESCE(water.band, 'unavailable')"
        conditions.append(f'{band}=ANY(:water_bands)')
    return f"{source} WHERE {' AND '.join(conditions)}", params


def st37_inventory_count(engine: Engine, import_id: UUID, filters: dict[str, list[str]], *,
                         water_comparison_ids: tuple[UUID, ...] = ()) -> int:
    selection, params = inventory_selection(import_id, filters, '', water_comparison_ids)
    with engine.connect() as conn:
        return conn.execute(text(f'SELECT count(*) FROM {selection}'), params).scalar_one()


def st37_inventory_page(engine: Engine, import_id: UUID, *, offset: int = 0, licence: str = '',
                        filters: dict[str, list[str]] | None = None,
                        water_comparison_ids: tuple[UUID, ...] = ()) -> list[dict]:
    """Read at most one page of original worksheet values from the selected snapshot."""
    selection, params = inventory_selection(import_id, filters, licence, water_comparison_ids)
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(text(f'''SELECT well.source_row, well.raw_payload,
            well.validation_errors, well.quality_warnings FROM {selection}
            ORDER BY well.source_row LIMIT :limit OFFSET :offset'''),
            params | {'limit': ST37_INVENTORY_PAGE_SIZE, 'offset': offset}).mappings()]


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
def import_st37_workbook(engine, workbook: Path, raw_root: Path, *, progress=lambda _: None):
    """Stage the retained workbook using the recorded datum only for the verified release."""
    area = load_study_area(ROOT / 'config/study_area.live.yml')
    report_path = retained_st37_report(workbook, area, raw_root, progress=progress)
    report = read_prepared_st37(report_path)
    try:
        datum = json.loads(ST37_DATUM_EVIDENCE.read_bytes())
    except FileNotFoundError:
        datum = {}
    declaration = {}
    if report['source']['sha256'] == datum.get('workbook_sha256'):
        declaration = {
            'coordinate_crs': datum['geodatabase']['geometry_base_crs'],
            'crs_evidence': datum['crs_evidence'],
            'release_date': datum['release_date'],
        }
    progress('Staging the complete ST37 inventory in PostGIS')
    return import_st37(engine, report_path, license_note=ST37_LICENSE_NOTE, **declaration)


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
